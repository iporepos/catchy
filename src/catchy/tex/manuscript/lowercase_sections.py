#!/usr/bin/env python3
"""Apply sentence-case to LaTeX section/subsection/subsubsection titles.

Architectural context
----------------------
Part of the Tier 1 -> Tier 2 LaTeX conversion pipeline for "Catchment
Hydrology: An Integrated Treatment Across Scales". Tier 1 headings are
often imported from Word with title-case capitalisation. Tier 2 convention
is sentence case: only the first word and protected tokens (acronyms,
proper nouns) are capitalised.

:func:`lowercase_sections` is written as a single self-contained function --
every constant, regex, and helper it needs is defined inside it -- so it
can be lifted as-is (e.g. as a ``@staticmethod``) into another module
without bringing along separate top-level dependencies.

The CLI (``main``) follows the same ``--chapter``/``-c`` convention and
``backup/``-folder backup behaviour as ``convert_workedexample.py`` /
``replace_from_csv.py``.

Usage
-----
    python lowercase_sections.py --chapter 3
    python lowercase_sections.py -c 3 --dry-run   # report changes, no write

Operates on ``chapter<NN>_T12.tex`` in the current directory (chapter
number zero-padded to two digits), in place (after a timestamped backup
into ``backup/``).

Dependencies
------------
Standard library only (``re``, ``argparse``, ``pathlib``, ``shutil``,
``datetime``).
"""

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def backup_file(src):
    bkp_folder = src.parent / "backup"
    bkp_folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    backup = bkp_folder / src.with_name(src.stem + '_' + ts + src.suffix)
    shutil.copy(src, backup)


def lowercase_sections(input_tex, output_tex=None):
    """Apply sentence-case to all sectioning command titles in a LaTeX file.

    Reads ``input_tex``, converts every ``\\section``, ``\\subsection``, and
    ``\\subsubsection`` title (starred forms included) from title-case to
    sentence case, and writes the result to ``output_tex``.

    This function performs no backup of its own. When ``output_tex`` is
    ``None`` (or equal to ``input_tex``), the input file is overwritten in
    place; callers that want a safety copy should take one beforehand (see
    :func:`backup_file`).

    :param input_tex: Path to the source ``.tex`` file to read.
    :type input_tex: str or pathlib.Path
    :param output_tex: Path to write the result to. If ``None`` (the
        default), ``input_tex`` is overwritten in place.
    :type output_tex: str or pathlib.Path or None

    :returns: ``(output_path, changed_count)`` -- the path written to and
        the number of lines that were modified.
    :rtype: tuple[pathlib.Path, int]

    :raises FileNotFoundError: If ``input_tex`` does not exist.
    :raises UnicodeDecodeError: If ``input_tex`` is not valid UTF-8.

    Sentence-case rules
    -------------------
    * The very first plain-text word is left as-is.
    * Every subsequent plain-text word is lowercased UNLESS:

      - It is two or more characters of uppercase letters / digits only
        (acronym heuristic): ``SWOT``, ``UNESCO``, ``ERA5``, ``API``.
      - It is listed in the ``PROPER_NOUNS`` set defined inside this
        function. Extend that set as proper nouns are encountered.

    * LaTeX commands (``\\emph{...}``, ``\\ac{...}``) and bare brace groups
      are passed through verbatim -- only the plain-text words between them
      are touched.
    * Lines where the closing brace does not appear on the same line
      (multi-line titles) are left untouched.

    Idempotent: a second run produces zero changes.

    Example
    -------
    .. code-block:: python

        from pathlib import Path
        lowercase_sections(Path("chapter03_T12.tex"))          # in place
        lowercase_sections("in.tex", "out.tex")                # new file
        path, n = lowercase_sections("chapter03_T12.tex")
        print(f"{n} heading(s) converted")
    """
    import re

    # ------------------------------------------------------------------
    # Customisation: tokens that must never be lowercased
    # ------------------------------------------------------------------

    PROPER_NOUNS = {
        "Earth",
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    }

    # All-caps token heuristic: 2+ chars, only uppercase letters and digits.
    ALLCAPS_RE = re.compile(r'^[A-Z0-9]{2,}$')

    # Tokeniser: LaTeX command (with optional brace group) | bare brace
    # group | plain word | whitespace run.
    TOKEN_RE = re.compile(
        r'('
        r'\\[a-zA-Z@]+\*?(?:\{[^}]*\})*'   # \cmd  or  \cmd{arg}
        r'|\{[^}]*\}'                        # {bare group}
        r'|[^\s\\{}]+'                       # plain word
        r'|\s+'                              # whitespace
        r')'
    )

    # Matches \section, \subsection, \subsubsection (optional *).
    # Groups: (command + opening brace)(title)(closing brace + trailing space).
    SECTION_RE = re.compile(
        r'^(\s*\\(?:sub){0,2}section\*?\{)(.*?)(\}\s*)$'
    )

    # ------------------------------------------------------------------
    # Inner helpers
    # ------------------------------------------------------------------

    def sentence_case(title):
        """Return *title* converted to sentence case."""
        tokens = TOKEN_RE.findall(title)
        result = []
        first_seen = False
        for tok in tokens:
            if tok.startswith('\\') or tok.startswith('{'):
                result.append(tok)              # LaTeX token: verbatim
            elif not tok.strip():
                result.append(tok)              # whitespace: verbatim
            elif not first_seen:
                result.append(tok[0].upper() + tok[1:])  # first word: ensure capitalised
                first_seen = True
            elif ALLCAPS_RE.match(tok):
                result.append(tok)              # acronym: keep
            elif tok in PROPER_NOUNS:
                result.append(tok)              # proper noun: keep
            else:
                result.append(tok.lower())
        return ''.join(result)

    def process_line(line):
        m = SECTION_RE.match(line)
        if not m:
            return line
        prefix, title, suffix = m.group(1), m.group(2), m.group(3)
        return prefix + sentence_case(title) + suffix

    # ------------------------------------------------------------------
    # File transform
    # ------------------------------------------------------------------

    input_tex = Path(input_tex)
    output_tex = Path(output_tex) if output_tex is not None else input_tex

    lines = input_tex.read_text(encoding='utf-8').splitlines(keepends=True)
    new_lines = []
    changed = 0

    for line in lines:
        new_line = process_line(line)
        if new_line != line:
            changed += 1
        new_lines.append(new_line)

    output_tex.write_text(''.join(new_lines), encoding='utf-8')
    return output_tex, changed


def main():
    parser = argparse.ArgumentParser(
        description='Apply sentence-case to LaTeX section/subsection/subsubsection titles.'
    )
    parser.add_argument("--chapter", "-c", type=int, help="chapter number")
    parser.add_argument("--backup", "-b", action="store_true", help="chapter number")
    parser.add_argument("--tier", "-t", type=str, default="12", help="chapter tier")
    args = parser.parse_args()
    c = str(args.chapter).zfill(2)
    c_t12 = f"chapter{c}_T{args.tier}.tex"
    src = Path(c_t12)

    if not src.exists():
        print(f"Error: file not found: {src}")
        sys.exit(1)

    if args.backup:
        backup_file(src)

    _, changed = lowercase_sections(src)
    print(f'[lowercase_sections] {src.name}: {changed} heading(s) converted.')
    print(f'[lowercase_sections] Wrote to {src}')


if __name__ == '__main__':
    main()