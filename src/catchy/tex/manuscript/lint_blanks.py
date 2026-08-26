#!/usr/bin/env python3
"""Normalize blank-line spacing in LaTeX source files.

Architectural context
----------------------
Part of the Tier 1 -> Tier 2 LaTeX pipeline for "Catchment Hydrology: An
Integrated Treatment Across Scales". Source files often arrive with
inconsistent vertical spacing. :func:`normalize_blank_lines` enforces two
rules simultaneously:

1. **Paragraph separation** -- any run of two or more consecutive blank
   lines in prose is collapsed to exactly one blank line.
2. **Environment padding** -- every ``\\begin{...}`` is preceded by exactly
   two blank lines, and every ``\\end{...}`` is followed by exactly two
   blank lines. The interior of the environment is left completely untouched.

Both rules leave the preamble and the interiors of non-reflowable
environments untouched.

:func:`normalize_blank_lines` is written as a single self-contained function
-- every constant, regex, and helper it needs is defined inside it -- so it
can be lifted as-is (e.g. as a ``@staticmethod``) into another module
without bringing along separate top-level dependencies.

Usage
-----
    python normalize_blank_lines.py --chapter 7
    python normalize_blank_lines.py -c 7

Operates on ``chapter07_T12.tex`` in the current directory (chapter number
zero-padded to two digits), in place (after a timestamped backup into
``backup/``).

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


def normalize_blank_lines(input_tex, output_tex=None):
    """
    Normalize blank-line spacing in a LaTeX file.

    Reads ``input_tex`` and enforces two rules throughout the document body:

    * **Paragraph separation** -- any run of two or more consecutive blank
      lines in prose is collapsed to exactly one blank line.
    * **Environment padding** -- every ``\\begin{...}`` is preceded by
      exactly two blank lines, and every ``\\end{...}`` is followed by
      exactly two blank lines. The interior of every environment (everything
      between its ``\\begin`` and ``\\end``) is left completely untouched.

    Schematically, the target layout is::

        <prose>

        <blank>
        <blank>
        \\begin{equation}
          ...            <- interior: never touched
        \\end{equation}
        <blank>
        <blank>
        <prose>

    Nested environments produce nested padding::

        <blank>
        <blank>
        \\begin{subequations}

          <blank>
          <blank>
          \\begin{align}
            ...
          \\end{align}
          <blank>
          <blank>

        \\end{subequations}
        <blank>
        <blank>

    The preamble (everything up to and including ``\\begin{document}``) and
    the document environment boundary itself are exempt from padding.

    This function performs no backup of its own. When ``output_tex`` is
    ``None`` (or equal to ``input_tex``), the input file is overwritten in
    place; callers that want a safety copy should take one beforehand.

    :param input_tex: Path to the source ``.tex`` file to read.
    :type input_tex: str or pathlib.Path
    :param output_tex: Path to write the result to. If ``None`` (the
        default), ``input_tex`` is overwritten in place.
    :type output_tex: str or pathlib.Path or None

    :returns: ``(output_path, stats)`` where ``stats`` is a dict with keys
        ``collapsed`` (excess blank lines removed) and ``padded`` (blank
        lines inserted).
    :rtype: tuple[pathlib.Path, dict]

    :raises FileNotFoundError: If ``input_tex`` does not exist.
    :raises UnicodeDecodeError: If ``input_tex`` is not valid UTF-8.

    Algorithm
    ---------
    A single forward pass over the lines maintains:

    * ``env_depth`` -- nesting depth of padded environments (0 = prose).
    * ``pending_pad`` -- number of blank lines still to be emitted after
      an ``\\end{...}`` before the next non-blank content.

    When a ``\\begin{...}`` is encountered (outside the preamble and outside
    the document environment): any trailing blank lines in the output buffer
    are stripped, exactly two blank lines are inserted, and then the
    ``\\begin`` line itself is emitted. ``env_depth`` is incremented, and
    all subsequent lines (including blank ones) are passed through verbatim
    until the matching ``\\end{...}`` is reached. On ``\\end{...}``:
    ``env_depth`` is decremented, the ``\\end`` line is emitted, and
    ``pending_pad`` is set to 2. The next non-blank line flushes those two
    blank lines first. Any blank lines in the source between ``\\end`` and
    the next content are discarded (replaced by the controlled padding).

    Example
    -------
    .. code-block:: python

        from pathlib import Path
        normalize_blank_lines(Path("chapter07_T12.tex"))
        path, stats = normalize_blank_lines("chapter07_T12.tex")
        print(f"{stats['collapsed']} blank(s) removed, "
              f"{stats['padded']} blank(s) inserted")
    """
    import re

    PAD = 2   # blank lines required before \begin and after \end

    # Environments exempt from padding (structural wrappers)
    NO_PAD_ENVS = {'document'}

    BEGIN_RE = re.compile(r'^\s*\\begin\{([^}]+)\}')
    END_RE   = re.compile(r'^\s*\\end\{([^}]+)\}')

    def is_blank(line):
        return line.strip() == ''

    def strip_trailing_blanks(lst):
        """Remove trailing blank lines from lst; return count removed."""
        n = 0
        while lst and is_blank(lst[-1]):
            lst.pop()
            n += 1
        return n

    # ------------------------------------------------------------------
    input_tex  = Path(input_tex)
    output_tex = Path(output_tex) if output_tex is not None else input_tex

    lines = input_tex.read_text(encoding='utf-8').split('\n')

    out = []
    n_collapsed  = 0
    n_padded     = 0

    seen_begin_doc = False
    seen_end_doc   = False

    # env_depth > 0 means we are inside a padded environment: pass verbatim
    env_depth    = 0
    # env_stack tracks names so nested \end matches correctly
    env_stack    = []
    # pending_pad: blank lines to emit before the next non-blank content
    # (set after \end so we control the post-environment spacing)
    pending_pad  = 0
    # consecutive blank lines in prose (for collapsing)
    prose_blanks = 0

    for line in lines:

        # ----------------------------------------------------------------
        # Preamble and post-document: verbatim
        # ----------------------------------------------------------------
        if not seen_begin_doc or seen_end_doc:
            out.append(line)
            m = BEGIN_RE.match(line)
            if m and m.group(1) == 'document':
                seen_begin_doc = True
            continue

        # ----------------------------------------------------------------
        # Inside a padded environment: pass everything verbatim
        # ----------------------------------------------------------------
        if env_depth > 0:
            m_end = END_RE.match(line)
            if m_end and env_stack and env_stack[-1] == m_end.group(1):
                env_name = env_stack.pop()
                env_depth -= 1
                out.append(line)
                if env_name not in NO_PAD_ENVS:
                    # Consume any source blank lines after \end
                    # (we will emit our own controlled padding instead)
                    pending_pad  = PAD
                    prose_blanks = 0
                if env_name == 'document':
                    seen_end_doc = True
            else:
                # Check for nested \begin inside the environment
                m_begin = BEGIN_RE.match(line)
                if m_begin:
                    env_stack.append(m_begin.group(1))
                    env_depth += 1
                out.append(line)
            continue

        # ----------------------------------------------------------------
        # Prose region
        # ----------------------------------------------------------------
        m_begin = BEGIN_RE.match(line)
        m_end   = END_RE.match(line)   # should not normally occur here

        if m_begin:
            env_name = m_begin.group(1)
            if env_name in NO_PAD_ENVS:
                # document begin: no padding, just track
                out.append(line)
                env_stack.append(env_name)
                env_depth += 1
                seen_begin_doc = True
            else:
                # Enforce PAD blank lines before \begin
                n_removed = strip_trailing_blanks(out)
                n_collapsed += max(0, n_removed - PAD)  # excess that were there
                out.extend([''] * PAD)
                n_padded += PAD
                out.append(line)
                env_stack.append(env_name)
                env_depth += 1
                prose_blanks = 0
                pending_pad  = 0
            continue

        # Blank line in prose
        if is_blank(line):
            if pending_pad > 0:
                # Discard source blanks after \end; we control the padding
                pass
            else:
                prose_blanks += 1
                if prose_blanks <= 1:
                    out.append(line)
                else:
                    n_collapsed += 1
            continue

        # Non-blank, non-begin line in prose
        if pending_pad > 0:
            # Emit the controlled post-\end padding then this line
            out.extend([''] * pending_pad)
            n_padded    += pending_pad
            pending_pad  = 0
        prose_blanks = 0
        out.append(line)

    output_tex.write_text('\n'.join(out), encoding='utf-8')
    return output_tex, {'collapsed': n_collapsed, 'padded': n_padded}


def main():
    parser = argparse.ArgumentParser(
        description='Normalize blank-line spacing: collapse prose runs to '
                    'one blank line; pad \\begin/\\end boundaries with '
                    'exactly two blank lines outside the environment.'
    )
    parser.add_argument('--chapter', '-c', type=int, required=True,
                        help='chapter number')
    args = parser.parse_args()

    c = str(args.chapter).zfill(2)
    input_file = Path(f'chapter{c}_T12.tex')

    if not input_file.exists():
        print(f'Error: file not found: {input_file}')
        raise SystemExit(1)

    backup_file(input_file)
    _, stats = normalize_blank_lines(input_file)
    print(f'[normalize_blank_lines] {input_file.name}: '
          f'{stats["collapsed"]} excess blank(s) collapsed, '
          f'{stats["padded"]} blank(s) inserted for environment padding.')
    print(f'[normalize_blank_lines] Wrote to {input_file.name}')


if __name__ == '__main__':
    main()