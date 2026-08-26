#!/usr/bin/env python3
"""Join wrapped source lines within each prose paragraph into a single line.

Architectural context
----------------------
Part of the Tier 1 -> Tier 2 LaTeX pipeline for "Catchment Hydrology: An
Integrated Treatment Across Scales". Source paragraphs are currently
hand-wrapped at a fixed column width, which means a single-word edit to a
paragraph produces a diff touching every subsequent line of that paragraph
(reflow noise). :func:`lint_paragraphs` converts each prose paragraph to a
single source line ("one paragraph per line"), so future edits produce
minimal, reviewable diffs, while leaving math displays, tables, and the
preamble untouched.

:func:`lint_paragraphs` is written as a single self-contained function --
every constant, regex, and helper it needs is defined inside it -- so it
can be lifted as-is (e.g. as a ``@staticmethod``) into another module
without bringing along separate top-level dependencies.

The CLI (``main``) follows the same ``--chapter``/``-c`` convention and
``backup/``-folder backup behaviour as ``convert_workedexample.py`` /
``replace_from_csv.py``.

Usage
-----
    python join_paragraphs.py --chapter 7
    python join_paragraphs.py -c 7

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


def lint_paragraphs(input_tex, output_tex=None):
    """
    Join wrapped prose paragraphs in a LaTeX file into single lines.

    Reads ``input_tex``, joins each wrapped prose paragraph in the document
    body into a single source line, and writes the result to
    ``output_tex``.

    This function performs no backup of its own. When ``output_tex`` is
    ``None`` (or equal to ``input_tex``), the input file is overwritten in
    place; callers that want a safety copy should take one beforehand (see
    :func:`backup_file`).

    :param input_tex: Path to the source ``.tex`` file to read.
    :type input_tex: str or pathlib.Path
    :param output_tex: Path to write the linted result to. If ``None``
        (the default), ``input_tex`` is overwritten in place.
    :type output_tex: str or pathlib.Path or None

    :returns: The path the linted ``.tex`` was written to (equal to
        ``input_tex`` if ``output_tex`` was ``None``).
    :rtype: pathlib.Path

    :raises FileNotFoundError: If ``input_tex`` does not exist.
    :raises UnicodeDecodeError: If ``input_tex`` is not valid UTF-8.

    Algorithm
    ---------
    1. Everything up to and including ``\\begin{document}``, and everything
       from ``\\end{document}`` onward, is passed through unchanged. (The
       preamble's ``\\newcommand`` shorthand definitions are one-per-line by
       convention and must stay that way.)
    2. Within the document body, consecutive lines are grouped into
       "paragraphs": maximal runs of lines that are not blank, not
       ``\\begin{...}``/``\\end{...}``, not comment-only, and not inside a
       non-reflowable environment. Each run is joined into a single line:
       every line is stripped of leading/trailing whitespace, joined with a
       single space, and any remaining runs of spaces are collapsed to one.
    3. The following end the current paragraph and are emitted unchanged on
       their own line, without being joined to anything: blank lines;
       ``\\begin{...}``/``\\end{...}`` lines (which also push/pop an
       environment stack used to track non-reflowable regions, including
       nested ones, by scanning the *whole* line -- e.g. a ``pmatrix``
       opened and closed on the same line inside an ``equation``/``align``
       nets to zero rather than leaking a permanently elevated
       non-reflowable count); a comment-only line that appears *between*
       paragraphs; and ``\\[``/``\\]`` display-math delimiters on their own
       line (tracked like a pseudo-environment), or inline ``\\[ ... \\]``
       on one line.
    4. A ``%`` comment that appears *inside* a paragraph -- either a
       comment-only line with real content already buffered, or a trailing
       ``% ...`` after real content -- does **not** split the paragraph.
       The real content (if any) is kept in the paragraph, and the comment
       text is deferred and appended to the end of the paragraph's joined
       line once it is flushed. This avoids an editorial comment in the
       middle of a sentence cutting it into two "paragraphs", the second
       starting mid-sentence (lower-case).
    5. ``\\item`` always starts a new paragraph (flush before it), but its
       own wrapped continuation lines still join onto it -- so consecutive
       list items each end up on their own line.
    6. The following commands always stand alone on their own output line,
       never merged with the paragraph before or after them, even without a
       blank line in the source: ``\\tcblower``, ``\\newpage``,
       ``\\clearpage``, ``\\cleardoublepage``, ``\\pagebreak``, ``\\newline``,
       ``\\figplaceholder``, ``\\boxfigplaceholder``,
       ``\\boxbiofigplaceholder``, and ``\\chapter``/``\\section``/
       ``\\subsection``/``\\subsubsection`` (starred or not).
    7. Non-reflowable environments (passed through verbatim, line-by-line,
       including any blank lines inside them): ``equation``, ``align``,
       ``gather``, ``multline``, ``eqnarray``, ``alignat`` and their starred
       forms; ``array``, ``cases``, ``matrix``/``pmatrix``/``bmatrix``/
       ``vmatrix``/``Vmatrix``; ``tabular``, ``tabular*``, ``tabularx``,
       ``longtable``; ``verbatim``, ``lstlisting``, ``minted``, ``Verbatim``;
       and ``\\[ ... \\]`` display math.

    .. note::
       Only line breaks and runs of whitespace within a joined paragraph
       are changed; no other characters are altered, so the rendered PDF
       is unaffected.

    Example
    -------
    .. code-block:: python

        from pathlib import Path
        lint_paragraphs(Path("chapter07_T12.tex"))  # overwrite in place
        lint_paragraphs("chapter07_T12.tex", "chapter07_T12_linted.tex")
    """
    import re

    NO_REFLOW_ENVS = {
        'equation', 'equation*', 'align', 'align*', 'alignat', 'alignat*',
        'gather', 'gather*', 'multline', 'multline*', 'eqnarray', 'eqnarray*',
        'array', 'matrix', 'pmatrix', 'bmatrix', 'vmatrix', 'Vmatrix', 'cases',
        'tabular', 'tabular*', 'tabularx', 'longtable',
        'verbatim', 'verbatim*', 'lstlisting', 'minted', 'Verbatim',
        '$$displaymath$$',  # pseudo-name for \[ ... \]
    }

    BEGIN_RE = re.compile(r'^\s*\\begin\{([^}]+)\}')
    END_RE = re.compile(r'^\s*\\end\{([^}]+)\}')
    TOKEN_RE = re.compile(r'\\(begin|end)\{([^}]+)\}')
    DISPLAY_OPEN_RE = re.compile(r'^\s*\\\[\s*$')
    DISPLAY_CLOSE_RE = re.compile(r'^\s*\\\]\s*$')
    DISPLAY_INLINE_RE = re.compile(r'^\s*\\\[.*\\\]\s*$')

    # Commands that always stand alone on their own output line -- never
    # merged with the paragraph before or after them, even without a blank
    # line in the source. These are one-shot structural commands
    # (placeholders, page breaks, pure headings) rather than prose.
    STANDALONE_RE = re.compile(
        r'^\s*\\(tcblower|newpage|clearpage|cleardoublepage|pagebreak|newline'
        r'|figplaceholder|boxfigplaceholder|boxbiofigplaceholder'
        r'|chapter\*?|section\*?|subsection\*?|subsubsection\*?)\b'
    )

    # \item always starts a new paragraph (flush before it), but its own
    # wrapped continuation lines still join onto it.
    ITEM_RE = re.compile(r'^\s*\\item\b')

    def find_comment_pos(line):
        """Return the index of the first un-escaped '%' in line, or -1."""
        i = 0
        while True:
            idx = line.find('%', i)
            if idx == -1:
                return -1
            j = idx - 1
            nbs = 0
            while j >= 0 and line[j] == '\\':
                nbs += 1
                j -= 1
            if nbs % 2 == 0:
                return idx
            i = idx + 1

    def process_tokens(line, env_stack, no_reflow):
        """
        Scan the (non-comment part of the) line for every
        \\begin{name}/\\end{name} token, in order, and update env_stack /
        no_reflow for each. A \\begin{X}...\\end{X} pair on the same line
        (e.g. a pmatrix inside an equation) therefore nets to zero, instead
        of leaking a permanently elevated no_reflow count. Returns the
        updated no_reflow.
        """
        pos = find_comment_pos(line)
        scan_part = line if pos == -1 else line[:pos]
        for m in TOKEN_RE.finditer(scan_part):
            kind, env = m.group(1), m.group(2)
            if kind == 'begin':
                env_stack.append(env)
                if env in NO_REFLOW_ENVS:
                    no_reflow += 1
            else:
                if env_stack and env_stack[-1] == env:
                    env_stack.pop()
                if env in NO_REFLOW_ENVS:
                    no_reflow -= 1
        return no_reflow

    def join_paragraphs(text):
        """Join wrapped prose lines into one line per paragraph. Returns new text."""
        lines = text.split('\n')
        out = []
        buf = []
        env_stack = []
        no_reflow = 0
        seen_begin_document = False
        seen_end_document = False
        pending_comments = []

        def flush():
            if buf or pending_comments:
                joined = ' '.join(s.strip() for s in buf)
                joined = re.sub(r' {2,}', ' ', joined).strip()
                if pending_comments:
                    extra = ' '.join(c.strip() for c in pending_comments)
                    joined = f'{joined} {extra}'.strip()
                out.append(joined)
                buf.clear()
                pending_comments.clear()

        for line in lines:
            if not seen_begin_document or seen_end_document:
                out.append(line)
                m = BEGIN_RE.match(line)
                if m and m.group(1) == 'document':
                    seen_begin_document = True
                continue

            stripped = line.strip()
            in_noreflow = no_reflow > 0

            m_begin = BEGIN_RE.match(line)
            m_end = END_RE.match(line)

            if in_noreflow:
                out.append(line.rstrip())
                no_reflow = process_tokens(line, env_stack, no_reflow)
                if DISPLAY_CLOSE_RE.match(line):
                    if env_stack and env_stack[-1] == '$$displaymath$$':
                        env_stack.pop()
                        no_reflow -= 1
                continue

            # not currently inside a non-reflowable environment
            if stripped == '':
                flush()
                out.append('')
                continue

            if m_end:
                env = m_end.group(1)
                flush()
                out.append(line.rstrip())
                no_reflow = process_tokens(line, env_stack, no_reflow)
                if env == 'document':
                    seen_end_document = True
                continue

            if m_begin:
                flush()
                out.append(line.rstrip())
                no_reflow = process_tokens(line, env_stack, no_reflow)
                continue

            if DISPLAY_INLINE_RE.match(line):
                flush()
                out.append(line.rstrip())
                continue

            if DISPLAY_OPEN_RE.match(line):
                flush()
                out.append(line.rstrip())
                env_stack.append('$$displaymath$$')
                no_reflow += 1
                continue

            if STANDALONE_RE.match(line):
                flush()
                out.append(line.rstrip())
                continue

            if ITEM_RE.match(line):
                flush()
                # fall through: this line (and its wrapped continuation
                # lines) form their own paragraph

            comment_pos = find_comment_pos(line)
            if comment_pos != -1:
                before = line[:comment_pos]
                if before.strip() == '':
                    if buf:
                        # comment-only line in the middle of a paragraph:
                        # defer it to the end of this paragraph's joined
                        # line rather than splitting the paragraph here
                        pending_comments.append(line.strip())
                    else:
                        # comment-only line between paragraphs: stands alone
                        flush()
                        out.append(line.rstrip())
                    continue
                else:
                    # real content with a trailing comment: keep the
                    # content in the paragraph, defer the comment to the
                    # end of the joined line
                    buf.append(before)
                    pending_comments.append(line[comment_pos:].strip())
                    continue

            buf.append(line)

        flush()
        return '\n'.join(out)

    input_tex = Path(input_tex)
    output_tex = Path(output_tex) if output_tex is not None else input_tex

    text = input_tex.read_text(encoding='utf-8')
    new_text = join_paragraphs(text)

    output_tex.write_text(new_text, encoding='utf-8')
    return output_tex


def main():
    parser = argparse.ArgumentParser(
        description='Join wrapped prose lines into one line per paragraph '
                    '(math, tables, and the preamble are left untouched).'
    )
    parser.add_argument('--chapter', '-c', type=int, help='chapter number')
    args = parser.parse_args()

    c = str(args.chapter).zfill(2)
    input_file = Path(f"chapter{c}_T12.tex")

    backup_file(input_file)

    n_before = input_file.read_text(encoding='utf-8').count('\n') + 1

    lint_paragraphs(input_file)

    n_after = input_file.read_text(encoding='utf-8').count('\n') + 1

    print(f'[reflow] {input_file.name}: {n_before} lines -> {n_after} lines')
    print(f'[reflow] Wrote to {input_file.name}')


if __name__ == '__main__':
    main()