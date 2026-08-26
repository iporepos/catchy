r"""
convert_boxes.py
================
Converts Tier-1  \begin{boxenv} ... \end{boxenv}  blocks to the Tier-2
\begin{boxmain}[label=...]{Type}{Title} ... \end{boxmain}  pattern.

Usage
-----
    python convert_boxes.py myfile.tex
    python -m convert_boxes myfile.tex

The script always backs up the original file to  myfile_TS.tex  before
converting, overwriting any previous backup. The input file is then
updated in place.

Rules applied
-------------
* The first line inside every boxenv must be a bold heading:
      \textbf{Box X.Y Type: Title}\\[...]
  or  \textbf{Box X.Y Type: Title}\\
  Recognised types (case-insensitive): Measurement, Story.
  Any other text (or absent type) is treated as type "Note".

* The figure placeholder stub produced at Tier 1:
      % T2: replace with \includegraphics for fig:X.Y
      \begin{center}
        \fbox{\parbox{0.85\textwidth}{\centering [Figure X.Y]}}
      \end{center}
  ... is replaced by a single  \boxfigplaceholder{Box X.Y}  line.
  If no such stub is found the placeholder is still inserted as the first
  body line (all boxes carry a figure, per spec).

* Everything else between the heading and \end{boxenv} is kept verbatim
  as the body content.

Output
------
  /backup/myfile_20250605T143012.tex   -- timestamped backup (one per run, never overwritten)
  myfile.tex                   -- converted file (in place)
r"""

import re, shutil
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Full boxenv block (non-greedy, DOTALL)
BOX_BLOCK_RE = re.compile(r"\\begin\{boxenv\}(.*?)\\end\{boxenv\}", re.DOTALL)

# Bold heading line: \textbf{Box 15.2 Measurement: Some Title}\\[0.5em]
# Captures: number ("15.2"), type-word (optional), title remainder
HEADING_RE = re.compile(
    r"\\textbf\{"
    r"Box\s+([\d.]+)"  # group 1 -- box number, e.g. "15.2"
    r"(?:\s+(Measurement|Story|Biography))?"  # group 2 -- type keyword (optional)
    r"[:\s]*"  # optional colon/space separator
    r"(.*?)"  # group 3 -- title text
    r"\}"
    r"(?:\\\\(?:\[.*?\])?)?"  # optional \\[...] newline command
    r"\s*\n?",  # trailing whitespace / newline
    re.IGNORECASE,
)

# Tier-1 figure placeholder block (three-line or condensed variants)
# Matches the comment line plus the center/fbox block that follows
FIG_STUB_RE = re.compile(
    r"%\s*T2:\s*replace with \\includegraphics for (?:fig:[^\n]+)\n"
    r"\s*\\begin\{center\}\s*\n"
    r"\s*\\fbox\{\\parbox\{[^}]*\}\{\\centering\s*\[(?:Figure\s*[^\]]*)\]\}\}\s*\n"
    r"\s*\\end\{center\}",
    re.IGNORECASE,
)

# Fallback: simpler \fbox line without the surrounding center env
FBOX_SIMPLE_RE = re.compile(
    r"%\s*T2:\s*replace with \\includegraphics for (?:fig:[^\n]+)\n"
    r"\s*\\fbox\{\\parbox\{[^}]*\}\{\\centering\s*\[(?:Figure\s*[^\]]*)\]\}\}",
    re.IGNORECASE,
)

KNOWN_TYPES = {"measurement", "story", "biography"}

# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------


def backup_file(src):
    bkp_folder = src.parent / "backup"
    bkp_folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = bkp_folder / src.with_name(src.stem + "_" + ts + src.suffix)
    shutil.copy(src, backup)
    return backup


def parse_heading(inner: str) -> tuple[str, str, str, str]:
    r"""
    Parse the first \textbf{Box ...} line from the box interior.

    Returns (box_label, box_type, title, remaining_body).
    box_label  : e.g. "Box 15.2"
    box_type   : e.g. "Measurement"
    title      : e.g. "Surface Water and Ocean Topography (SWOT)"
    remaining_body : everything after the heading line
    r"""
    m = HEADING_RE.search(inner)
    if not m:
        # No recognisable heading -- treat entire interior as body
        return ("Box ?", "Note", "Unknown", inner.strip())

    number = m.group(1).strip()  # "15.2"
    type_raw = m.group(2) or ""  # "Measurement" or ""
    title = m.group(3).strip()  # "Surface Water ..."

    box_label = f"Box {number}"
    box_type = type_raw.capitalize() if type_raw.lower() in KNOWN_TYPES else "Note"

    # Strip the heading from the interior
    remaining = inner[m.end() :]
    return (box_label, box_type, title, remaining)


def replace_fig_stub(body: str, box_label: str) -> tuple[str, bool]:
    r"""
    Remove the T1 figure placeholder stub from body.
    Returns (cleaned_body, found_stub).
    r"""
    cleaned, n = FIG_STUB_RE.subn("", body, count=1)
    if n:
        return (cleaned, True)
    cleaned, n = FBOX_SIMPLE_RE.subn("", body, count=1)
    return (cleaned, bool(n))


def convert_block(match: re.Match) -> str:
    r"""Convert one \begin{boxenv}...\end{boxenv} match to boxmain.r"""
    inner = match.group(1)  # everything between begin/end tags

    box_label, box_type, title, body = parse_heading(inner)
    body, _found_stub = replace_fig_stub(body, box_label)

    # Clean up excessive blank lines left by stub removal
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    lines = [
        f"\\begin{{boxmain}}[label={box_label}]{{{box_type}}}{{{title}}}",
        f"\\boxfigplaceholder{{{box_label}}}",
    ]
    if body:
        lines.append(body)
    lines.append("\\end{boxmain}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File-level entry point
# ---------------------------------------------------------------------------


def convert_file(src: Path) -> None:

    backup = backup_file(src)
    print(f"[convert_boxes] Backup written to:  {backup}")

    text = src.read_text(encoding="utf-8")

    n_boxes = len(BOX_BLOCK_RE.findall(text))
    if n_boxes == 0:
        print(
            f"[convert_boxes] No \\begin{{boxenv}} blocks found in {src.name} -- nothing to do."
        )
        return

    # Convert and overwrite in place
    converted = BOX_BLOCK_RE.sub(convert_block, text)
    src.write_text(converted, encoding="utf-8")
    print(f"[convert_boxes] {n_boxes} box(es) converted.")
    print(f"[convert_boxes] File updated:        {src}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert T1 boxenv blocks to T2 boxmain pattern."
    )
    parser.add_argument("--chapter", "-c", type=int, help="chapter number")
    args = parser.parse_args()
    c = str(args.chapter).zfill(2)
    c_t12 = f"chapter{c}_T12.tex"
    src = Path(c_t12)

    if not src.exists():
        print(f"Error: file not found: {src}")
        sys.exit(1)

    convert_file(src)


if __name__ == "__main__":
    main()
