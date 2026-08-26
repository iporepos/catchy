#!/usr/bin/env python3
"""Remove decoration comments (no letter characters) from a LaTeX file.

Architectural context
----------------------
Part of the Tier 1 -> Tier 2 LaTeX pipeline for "Catchment Hydrology: An
Integrated Treatment Across Scales". Source files often contain horizontal-
rule comments such as ``%======``, ``%------``, ``% ~~~``, or bare ``%``
lines used purely as visual separators. These add noise to diffs and carry
no semantic content. :func:`purge_decoration_comments` removes them while
leaving every real comment (one whose text after the ``%`` contains at
least one ASCII letter) untouched.

:func:`purge_decoration_comments` is written as a single self-contained
function -- every constant, regex, and helper it needs is defined inside it
-- so it can be lifted as-is (e.g. as a ``@staticmethod``) into another
module without bringing along separate top-level dependencies.

The CLI (``main``) follows the same ``--chapter``/``-c`` convention and
``backup/``-folder backup behaviour as ``join_paragraphs.py`` /
``convert_workedexample.py`` / ``replace_from_csv.py``.

Usage
-----
    python purge_decoration_comments.py --chapter 7
    python purge_decoration_comments.py -c 7

Operates on ``chapter07_T12.tex`` in the current directory (chapter number
zero-padded to two digits), in place (after a timestamped backup into
``backup/``).

Dependencies
------------
Standard library only (``re``, ``argparse``, ``pathlib``, ``shutil``,
``datetime``).

What counts as a decoration comment
-------------------------------------
A comment is *decorative* if the text that follows the ``%`` (after
stripping leading/trailing whitespace) contains **no ASCII letter**
(``[A-Za-z]``). Examples that are removed:

    %
    %===
    % ---
    % ~~~
    %   !!!
    % 123
    % 42

Examples that are kept:

    % this is a note
    %TODO
    % see equation (3)
    %\\label{eq:foo}   <- backslash followed by a letter counts

Trailing decoration comments on prose lines
--------------------------------------------
If a prose line contains a trailing ``%`` whose suffix has no letters, that
suffix is stripped and the prose is kept (trailing whitespace trimmed).
Example::

    some text  % ====        ->  some text
    some text  % see below   ->  some text  % see below   (kept)

Blank-line collapse
--------------------
When a comment-only decoration line is removed, the blank line it would
leave behind is suppressed as well (net-zero change to the surrounding
vertical spacing). Consecutive blank lines that were already present before
the purge are not touched.

Scope control (document_only)
------------------------------
By default (``document_only=False``) the purge runs over the **entire
file**, including the preamble and any content after ``\\end{document}``.
Pass ``document_only=True`` to restrict processing to the body between
``\\begin{document}`` and ``\\end{document}``, leaving the preamble and
postamble untouched.

Exception characters (except_chars)
-------------------------------------
Pass a list of single characters to ``except_chars`` to protect any
decoration comment whose text (after ``%``) contains at least one of those
characters. Examples::

    except_chars=['#']   ->  % ####   is kept
    except_chars=['-']   ->  % -----  is kept
    except_chars=None    ->  all decoration comments are removed (default)
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


def purge_decoration_comments(input_tex, output_tex=None,
                              document_only=False, except_chars=None):
    """
    Remove decoration comments (no letter characters after ``%``) from a
    LaTeX file.

    Reads ``input_tex``, strips every decorative comment (comment-only lines
    and trailing comment suffixes on prose lines whose comment text contains
    no ASCII letter), and writes the result to ``output_tex``.

    This function performs no backup of its own. When ``output_tex`` is
    ``None`` (or equal to ``input_tex``), the input file is overwritten in
    place; callers that want a safety copy should take one beforehand (see
    :func:`backup_file`).

    :param input_tex: Path to the source ``.tex`` file to read.
    :type input_tex: str or pathlib.Path
    :param output_tex: Path to write the purged result to. If ``None``
        (the default), ``input_tex`` is overwritten in place.
    :type output_tex: str or pathlib.Path or None
    :param document_only: If ``False`` (the default), the purge runs over
        the entire file -- preamble, body, and postamble alike.  If ``True``,
        only the lines between ``\\begin{document}`` and ``\\end{document}``
        are processed; the preamble and postamble are passed through unchanged.
    :type document_only: bool
    :param except_chars: Optional list of single characters. A decoration
        comment (one whose text after ``%`` contains no ASCII letter) is
        nonetheless **kept** if its text contains at least one character from
        this list. Use this to preserve specific ruler styles, e.g.
        ``except_chars=['#']`` keeps ``% ####`` lines.  ``None`` (the
        default) means no exceptions -- all decoration comments are removed.
    :type except_chars: list[str] or None

    :returns: The path the purged ``.tex`` was written to (equal to
        ``input_tex`` if ``output_tex`` was ``None``).
    :rtype: pathlib.Path

    :raises FileNotFoundError: If ``input_tex`` does not exist.
    :raises UnicodeDecodeError: If ``input_tex`` is not valid UTF-8.

    Algorithm
    ---------
    1. When ``document_only=True``, everything up to and including
       ``\\begin{document}``, and everything from ``\\end{document}`` onward,
       is passed through unchanged.  When ``document_only=False`` (default),
       all lines -- including the preamble -- are processed uniformly.
    2. Within the processed region each line is classified as one of:

       a. **Blank** – passed through unchanged.
       b. **Comment-only decoration** – the entire line's non-whitespace
          content is a ``%`` whose following text (stripped) contains no
          ASCII letter and no ``except_chars`` character.  The line is
          *dropped*; if the previous output line was blank, that blank is
          also removed (blank-line collapse).
       c. **Comment-only kept** – comment-only but preserved because the
          text contains a letter or an ``except_chars`` character.  Passed
          through unchanged.
       d. **Prose with trailing decoration comment** – the ``%`` suffix
          qualifies as decoration.  The suffix (and any whitespace before
          it) is stripped; the prose remainder is kept.
       e. **Prose with trailing real comment** – kept verbatim.
       f. **Prose without any comment** – kept verbatim.

    3. The ``%`` position is found via ``_find_comment_pos``, which
       correctly handles escaped percent signs (``\\%``).
    4. Non-reflowable environments (``equation``, ``align``, ``tabular``,
       ``verbatim``, etc.) receive no special treatment here: comment lines
       inside math or table environments are still subject to the same rule.

    .. note::
       Only comment text is removed; no other characters are altered, so
       the rendered PDF is unaffected.

    Example
    -------
    .. code-block:: python

        from pathlib import Path
        # default: whole file, no exceptions
        purge_decoration_comments(Path("chapter07_T12.tex"))
        # body only, keep lines containing '#'
        purge_decoration_comments(
            "chapter07_T12.tex", "chapter07_T12_clean.tex",
            document_only=True, except_chars=['#'],
        )
    """
    import re

    BEGIN_DOCUMENT_RE = re.compile(r'^\s*\\begin\{document\}')
    END_DOCUMENT_RE = re.compile(r'^\s*\\end\{document\}')

    def _find_comment_pos(line):
        """Return the index of the first un-escaped '%' in *line*, or -1."""
        i = 0
        while True:
            idx = line.find('%', i)
            if idx == -1:
                return -1
            # count immediately preceding backslashes
            j = idx - 1
            nbs = 0
            while j >= 0 and line[j] == '\\':
                nbs += 1
                j -= 1
            if nbs % 2 == 0:   # even number of backslashes -> real %
                return idx
            i = idx + 1

    def _is_decoration(comment_text):
        """True when *comment_text* (text after the leading '%') should be removed.

        A comment qualifies as decoration when it contains no ASCII letter AND
        none of the characters in *except_chars* (captured from the outer
        scope).
        """
        if re.search(r'[A-Za-z]', comment_text):
            return False
        if except_chars and any(ch in comment_text for ch in except_chars):
            return False
        return True

    def _process_body(lines):
        """Apply decoration-comment purge to *lines*. Returns list of lines."""
        out = []

        for line in lines:
            # preserve blank lines as-is
            if line.strip() == '':
                out.append(line)
                continue

            comment_pos = _find_comment_pos(line)

            if comment_pos == -1:
                # no comment at all
                out.append(line)
                continue

            before = line[:comment_pos]          # prose part (may be empty)
            comment_text = line[comment_pos + 1:]  # everything after the %

            if before.strip() == '':
                # ---- comment-only line ----
                if _is_decoration(comment_text):
                    # drop this line; also collapse the preceding blank if present
                    if out and out[-1].strip() == '':
                        out.pop()
                    # do NOT append anything
                else:
                    out.append(line)
            else:
                # ---- prose line with a trailing comment ----
                if _is_decoration(comment_text):
                    # strip the comment suffix; rstrip any whitespace before %
                    out.append(before.rstrip())
                else:
                    out.append(line)

        return out

    # ------------------------------------------------------------------ #
    # Main entry: split into preamble / body / postamble, process body    #
    # ------------------------------------------------------------------ #
    input_tex = Path(input_tex)
    output_tex = Path(output_tex) if output_tex is not None else input_tex

    raw = input_tex.read_text(encoding='utf-8')
    lines = raw.split('\n')

    if not document_only:
        # Process the entire file uniformly -- no preamble/postamble split.
        result = '\n'.join(_process_body(lines))
    else:
        # Restrict processing to the body between \begin{document} and
        # \end{document}; preamble and postamble pass through unchanged.
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
        description='Remove decoration comments (no ASCII letters after %%) '
                    'from a LaTeX file.'
    )
    parser.add_argument('--chapter', '-c', type=int, required=True,
                        help='chapter number')
    args = parser.parse_args()

    c = str(args.chapter).zfill(2)
    input_file = Path(f"chapter{c}_T12.tex")

    backup_file(input_file)

    n_before = input_file.read_text(encoding='utf-8').count('\n') + 1

    purge_decoration_comments(input_file)

    n_after = input_file.read_text(encoding='utf-8').count('\n') + 1

    print(f'[purge] {input_file.name}: {n_before} lines -> {n_after} lines '
          f'({n_before - n_after} decoration comments removed)')
    print(f'[purge] Wrote to {input_file.name}')


if __name__ == '__main__':
    main()