#!/usr/bin/env python3
"""Remove every ``\\authornote{...}`` call from a LaTeX file.

Architectural context
----------------------
Part of the Tier 1 -> Tier 2 LaTeX pipeline for "Catchment Hydrology: An
Integrated Treatment Across Scales". During editing, manuscript files carry
author/editorial notes written with the macro defined in
``config_manuscript.tex``::

    \\newcommand{\\authornote}[1]{\\hl{[Author note: #1]}}

:func:`purge_authornotes` strips every call of that macro -- the command
*and* its braced argument -- so the file can be compiled clean for
publication. The macro definition itself is never touched (``\\authornote``
followed by ``}`` is not a call), so running the script on a file that
contains the preamble is safe.

:func:`purge_authornotes` is written as a single self-contained function --
every constant and helper it needs is defined inside it -- so it can be
lifted as-is into another module, following ``lint_purge_decorations.py``.

Usage
-----
    python lint_purge_authornotes.py path/to/chapter07_T12.tex
    python lint_purge_authornotes.py path/to/chapter07_T12.tex -o clean.tex

Without ``-o`` the file is modified in place, after a timestamped backup into
a ``backup/`` folder next to it. With ``-o`` the input is left untouched and
no backup is taken.

Dependencies
------------
Standard library only (``argparse``, ``pathlib``, ``shutil``, ``datetime``).

What is removed
----------------
Every ``\\authornote`` call followed by a braced argument (optional spaces
or tabs allowed between the macro and ``{``). The argument is matched by
brace counting, so nested groups and multi-line notes are removed whole::

    \\authornote{check this}
    \\authornote{see \\cref{eq:balance} and \\textbf{fix}}
    \\authornote{a note that
      spans two lines}

What is kept
-------------
- The macro definition (``\\newcommand{\\authornote}...``).
- Longer macro names such as ``\\authornotes{...}``.
- Calls inside ``%`` comments.
- Escaped braces (``\\{``, ``\\}``) and braces inside comments do not count
  toward the brace depth.

Whitespace handling
--------------------
- **Whole-line note** (only whitespace around it on its line(s)): the line
  is dropped. If that leaves two blank lines in a row, one is dropped too,
  so paragraph breaks are kept but not doubled.
- **Inline note followed by a space or tab**: that following whitespace is
  removed (``text \\authornote{x} more`` -> ``text more``).
- **Inline note followed by anything else** (punctuation, end of line): the
  preceding whitespace is removed (``text \\authornote{x}.`` -> ``text.``).

Line endings (LF or CRLF) are preserved.
"""

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def backup_file(src):
    bkp_folder = src.parent / "backup"
    bkp_folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    backup = bkp_folder / (src.stem + '_' + ts + src.suffix)
    shutil.copy(src, backup)


def purge_authornotes(input_tex, output_tex=None):
    """
    Remove every ``\\authornote{...}`` call from a LaTeX file.

    Performs no backup of its own; when ``output_tex`` is ``None`` the input
    file is overwritten in place (see :func:`backup_file`).

    :param input_tex: Path to the source ``.tex`` file to read.
    :type input_tex: str or pathlib.Path
    :param output_tex: Path to write the result to. If ``None`` (the
        default), ``input_tex`` is overwritten in place.
    :type output_tex: str or pathlib.Path or None
    :returns: Number of notes removed.
    :rtype: int
    :raises FileNotFoundError: If ``input_tex`` does not exist.
    :raises ValueError: If a note's braces are unbalanced (nothing is
        written in that case).
    """
    MACRO = '\\authornote'
    HSPACE = ' \t'

    def _skip_comment(text, i):
        """Return the index of the newline ending the comment at *i*."""
        nl = text.find('\n', i)
        return len(text) if nl == -1 else nl

    def _match_brace(text, k, start):
        """Return the index just past the '}' closing the '{' at *k*."""
        depth = 0
        i = k
        while i < len(text):
            ch = text[i]
            if ch == '\\':
                i += 2
                continue
            if ch == '%':
                i = _skip_comment(text, i)
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        line = text.count('\n', 0, start) + 1
        raise ValueError(f'unbalanced braces in {MACRO} at line {line}')

    def _find_notes(text):
        """Return (start, end) spans of every note call in *text*."""
        spans = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '%':
                i = _skip_comment(text, i)
                continue
            if ch != '\\':
                i += 1
                continue
            if not text.startswith(MACRO, i):
                # skip the backslash and the escaped / first command char
                i += 2
                continue
            j = i + len(MACRO)
            if j < len(text) and text[j].isalpha():
                # a longer macro name, e.g. \authornotes
                i = j
                continue
            k = j
            while k < len(text) and text[k] in HSPACE:
                k += 1
            if k >= len(text) or text[k] != '{':
                # not a call, e.g. \newcommand{\authornote}
                i = j
                continue
            end = _match_brace(text, k, i)
            spans.append((i, end))
            i = end
        return spans

    def _remove(text, start, end):
        """Cut the span [start, end) out of *text* and tidy whitespace."""
        ls = text.rfind('\n', 0, start) + 1
        le = text.find('\n', end)
        if le == -1:
            le = len(text)

        if text[ls:start].strip() == '' and text[end:le].strip() == '':
            # whole-line note: drop the line with its newline
            text = text[:ls] + text[le + 1:]
            if ls == 0:
                return text
            # collapse a blank line left between two blank lines
            pls = text.rfind('\n', 0, ls - 1) + 1
            nle = text.find('\n', ls)
            if (nle != -1 and text[pls:ls - 1].strip() == ''
                    and text[ls:nle].strip() == ''):
                text = text[:ls] + text[nle + 1:]
            return text

        if end < len(text) and text[end] in HSPACE:
            # inline, followed by spaces: drop the spaces after the note
            while end < len(text) and text[end] in HSPACE:
                end += 1
        else:
            # inline, followed by punctuation/EOL: drop the spaces before
            while start > ls and text[start - 1] in HSPACE:
                start -= 1
        return text[:start] + text[end:]

    input_tex = Path(input_tex)
    output_tex = Path(output_tex) if output_tex is not None else input_tex

    # newline='' keeps the file's own line endings (LF or CRLF)
    with open(input_tex, encoding='utf-8', newline='') as f:
        text = f.read()

    spans = _find_notes(text)
    # remove back to front so earlier spans keep their indices
    for start, end in reversed(spans):
        text = _remove(text, start, end)

    with open(output_tex, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    return len(spans)


def main():
    parser = argparse.ArgumentParser(
        description='Remove every \\authornote{...} call from a LaTeX file.'
    )
    parser.add_argument('path', type=Path, help='path to the .tex file')
    parser.add_argument('--output', '-o', type=Path, default=None,
                        help='write the result here instead of in place')
    args = parser.parse_args()

    input_file = args.path
    if not input_file.is_file():
        parser.error(f'file not found: {input_file}')

    if args.output is None:
        backup_file(input_file)

    n = purge_authornotes(input_file, args.output)

    output_file = args.output or input_file
    print(f'[authornotes] {input_file.name}: {n} notes removed')
    print(f'[authornotes] Wrote to {output_file}')


if __name__ == '__main__':
    main()
