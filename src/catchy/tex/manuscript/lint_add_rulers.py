#!/usr/bin/env python3
"""Inject decoration rulers above section headings in a LaTeX file.

Architectural context
----------------------
Part of the Tier 1 -> Tier 2 LaTeX pipeline for "Catchment Hydrology: An
Integrated Treatment Across Scales". Companion to
``purge_decoration_comments.py``: where that script removes letter-free
comment rulers, this one inserts them, providing a consistent visual
separator in the source above every structural heading.

:func:`inject_section_rulers` is written as a single self-contained
function -- every constant, regex, and helper it needs is defined inside it
-- so it can be lifted as-is (e.g. as a ``@staticmethod``) into another
module without bringing along separate top-level dependencies.

The CLI (``main``) follows the same ``--chapter``/``-c`` convention and
``backup/``-folder backup behaviour as ``purge_decoration_comments.py`` /
``join_paragraphs.py`` / ``convert_workedexample.py``.

Usage
-----
    python inject_section_rulers.py --chapter 7
    python inject_section_rulers.py -c 7 --ruler-chars "#*=-" --ruler-len 72

Operates on ``chapter07_T12.tex`` in the current directory (chapter number
zero-padded to two digits), in place (after a timestamped backup into
``backup/``).

Dependencies
------------
Standard library only (``re``, ``argparse``, ``pathlib``, ``shutil``,
``datetime``).

Heading levels and default ruler characters
--------------------------------------------
Rulers are injected only inside the document body (between
``\\begin{document}`` and ``\\end{document}``).  The preamble and postamble
are passed through unchanged.

Four heading levels are recognised (starred and unstarred alike):

    Level 1  ``\\chapter``        ->  ``% ############...``   (default char ``#``)
    Level 2  ``\\section``        ->  ``% ************...``   (default char ``*``)
    Level 3  ``\\subsection``     ->  ``% ============...``   (default char ``=``)
    Level 4  ``\\subsubsection``  ->  ``% ------------...``   (default char ``-``)

The ruler is always placed on the line immediately **before** the heading
command.  If a ruler with the same character already exists on that line,
it is replaced rather than duplicated (idempotent re-runs).

Ruler format
-------------
Each ruler is ``% `` followed by ``N`` repetitions of the level character::

    % ############################################################   (N=60)

``N`` defaults to 60 and is controlled by the ``ruler_len`` parameter /
``--ruler-len`` CLI flag.

Custom ruler characters
------------------------
Pass a sequence of up to four characters via ``ruler_chars`` to override the
defaults for each level.  The sequence is positional (index 0 = chapter,
1 = section, 2 = subsection, 3 = subsubsection).  If the sequence is
shorter than four elements the remaining levels fall back to the defaults::

    ruler_chars='#*'   ->  chapter='#', section='*',
                            subsection='=' (default), subsubsection='-' (default)
    ruler_chars='@'    ->  chapter='@', rest default
"""

import argparse
import re
import shutil
from datetime import datetime
from pathlib import Path


def backup_file(src):
    bkp_folder = src.parent / "backup"
    bkp_folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    backup = bkp_folder / src.with_name(src.stem + '_' + ts + src.suffix)
    shutil.copy(src, backup)


def inject_section_rulers(input_tex, output_tex=None,
                           ruler_chars=None, ruler_len=60):
    """
    Inject decoration rulers above section headings in a LaTeX file.

    Reads ``input_tex``, inserts a comment ruler (``% `` + N repetitions of
    a level-specific character) on the line immediately before every
    ``\\chapter``, ``\\section``, ``\\subsection``, and ``\\subsubsection``
    command found inside the document body, then writes the result to
    ``output_tex``.

    The preamble (everything up to and including ``\\begin{document}``) and
    the postamble (``\\end{document}`` and everything after) are passed
    through unchanged.

    If a ruler with the correct character already exists on the line
    immediately before a heading, it is **replaced** rather than duplicated,
    making the function safe to call multiple times on the same file
    (idempotent with respect to ruler content; ruler length is always
    normalised to the current ``ruler_len``).

    This function performs no backup of its own. When ``output_tex`` is
    ``None`` (or equal to ``input_tex``), the input file is overwritten in
    place; callers that want a safety copy should take one beforehand (see
    :func:`backup_file`).

    :param input_tex: Path to the source ``.tex`` file to read.
    :type input_tex: str or pathlib.Path
    :param output_tex: Path to write the result to.  If ``None`` (the
        default), ``input_tex`` is overwritten in place.
    :type output_tex: str or pathlib.Path or None
    :param ruler_chars: Sequence of up to four characters, one per heading
        level (chapter, section, subsection, subsubsection).  Missing
        positions fall back to the defaults ``('#', '*', '=', '-')``.
        May be a string (each character is used positionally) or any
        sequence of single characters.  ``None`` uses all defaults.
    :type ruler_chars: str or list[str] or None
    :param ruler_len: Number of times the ruler character is repeated after
        the ``% `` prefix.  Defaults to ``60``.
    :type ruler_len: int

    :returns: The path the result was written to.
    :rtype: pathlib.Path

    :raises FileNotFoundError: If ``input_tex`` does not exist.
    :raises UnicodeDecodeError: If ``input_tex`` is not valid UTF-8.
    :raises ValueError: If ``ruler_len`` is less than 1.

    Algorithm
    ---------
    1. Split the file into preamble, body lines, and postamble at
       ``\\begin{document}`` / ``\\end{document}``.  Only the body is
       processed.
    2. Resolve the four ruler strings from ``ruler_chars`` and ``ruler_len``.
    3. Walk body lines.  When a line matches a heading command, look at the
       previous output line:

       - If it is already a ruler whose dominant character matches the
         current level's character, **replace** it with the freshly built
         ruler (normalises length on re-runs).
       - Otherwise **insert** the ruler as a new line before the heading.

    4. Reassemble preamble + processed body + postamble and write.

    .. note::
       A "ruler line" for replacement detection is defined as a line whose
       stripped content matches ``% <char><char>...`` with at least one
       repetition of *char* -- the same format this function produces.
       Any other comment line is left untouched even if it precedes a
       heading.

    Example
    -------
    .. code-block:: python

        from pathlib import Path
        # defaults: #/*=/- at length 60
        inject_section_rulers(Path("chapter07_T12.tex"))
        # custom chars, length 72
        inject_section_rulers(
            "chapter07_T12.tex", "chapter07_T12_ruled.tex",
            ruler_chars="#*=-", ruler_len=72,
        )
    """
    if ruler_len < 1:
        raise ValueError(f"ruler_len must be >= 1, got {ruler_len!r}")

    DEFAULTS = ('#', '*', '=', '-')
    LEVELS = ('chapter', 'section', 'subsection', 'subsubsection')

    # Resolve ruler characters: positional override, fall back to defaults.
    resolved_chars = list(DEFAULTS)
    if ruler_chars is not None:
        for i, ch in enumerate(ruler_chars):
            if i >= 4:
                break
            resolved_chars[i] = ch

    # Build the four ruler strings and their detection regexes.
    rulers = {}       # level_name -> ruler string
    ruler_res = {}    # level_name -> compiled regex that matches any ruler for that level
    for level, ch in zip(LEVELS, resolved_chars):
        rulers[level] = f'% {ch * ruler_len}'
        escaped = re.escape(ch)
        ruler_res[level] = re.compile(rf'^\s*%\s*{escaped}+\s*$')

    # Heading detection: \chapter, \section, \subsection, \subsubsection
    # (starred or unstarred), optionally followed by [] optional arg or {}.
    HEADING_RE = re.compile(
        r'^\s*\\(chapter|section|subsection|subsubsection)\*?\s*[\[{]'
    )

    BEGIN_DOCUMENT_RE = re.compile(r'^\s*\\begin\{document\}')
    END_DOCUMENT_RE = re.compile(r'^\s*\\end\{document\}')

    def _level_of(line):
        """Return the heading level name if *line* is a heading, else None."""
        m = HEADING_RE.match(line)
        return m.group(1) if m else None

    def _process_body(lines):
        """Inject rulers above headings. Returns new list of lines."""
        out = []
        for line in lines:
            level = _level_of(line)
            if level is None:
                out.append(line)
                continue

            ruler = rulers[level]
            ruler_re = ruler_res[level]

            # Check whether the previous output line is already a ruler for
            # this level; if so, replace it (idempotent).
            if out and ruler_re.match(out[-1]):
                out[-1] = ruler
            else:
                out.append(ruler)

            out.append(line)

        return out

    # ------------------------------------------------------------------ #
    # Split, process body, reassemble                                      #
    # ------------------------------------------------------------------ #
    input_tex = Path(input_tex)
    output_tex = Path(output_tex) if output_tex is not None else input_tex

    raw = input_tex.read_text(encoding='utf-8')
    lines = raw.split('\n')

    preamble = []
    body_raw = []
    postamble = []

    seen_begin = False
    seen_end = False

    for line in lines:
        if not seen_begin:
            preamble.append(line)
            if BEGIN_DOCUMENT_RE.match(line):
                seen_begin = True
        elif seen_end:
            postamble.append(line)
        else:
            if END_DOCUMENT_RE.match(line):
                seen_end = True
                postamble.append(line)
            else:
                body_raw.append(line)

    body_clean = _process_body(body_raw)

    result = '\n'.join(preamble + body_clean + postamble)
    output_tex.write_text(result, encoding='utf-8')
    return output_tex


def main():
    parser = argparse.ArgumentParser(
        description='Inject decoration rulers above section headings in a '
                    'LaTeX file (only inside the document body).'
    )
    parser.add_argument('--chapter', '-c', type=int, required=True,
                        help='chapter number')
    parser.add_argument('--ruler-chars', '-r', metavar='CHARS', default=None,
                        help='up to four characters, one per heading level '
                             '(chapter, section, subsection, subsubsection). '
                             'Example: --ruler-chars "#*=-"  '
                             'Missing positions fall back to defaults: #, *, =, -')
    parser.add_argument('--ruler-len', '-n', type=int, default=60,
                        help='number of repetitions of the ruler character '
                             '(default: 60)')
    args = parser.parse_args()

    c = str(args.chapter).zfill(2)
    input_file = Path(f"chapter{c}_T12.tex")

    backup_file(input_file)

    n_before = input_file.read_text(encoding='utf-8').count('\n') + 1

    inject_section_rulers(input_file,
                          ruler_chars=args.ruler_chars,
                          ruler_len=args.ruler_len)

    n_after = input_file.read_text(encoding='utf-8').count('\n') + 1

    print(f'[inject] {input_file.name}: {n_before} lines -> {n_after} lines '
          f'({n_after - n_before} rulers injected)')
    print(f'[inject] Wrote to {input_file.name}')


if __name__ == '__main__':
    main()