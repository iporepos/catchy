#!/usr/bin/env python3
"""Convert legacy ``workedex`` environments to the new ``workedexample`` environment.

Architectural context
----------------------
Part of the Tier 1 -> Tier 2 LaTeX conversion pipeline for "Catchment
Hydrology: An Integrated Treatment Across Scales". Tier 1 chapters contain
manually-numbered worked examples:

    \\begin{workedex}{Worked example W7.1: Title text}
    \\textbf{Problem:} ...
    \\textbf{Solution:} ...
    \\end{workedex}

Tier 2 replaces ``workedex`` with the auto-numbered ``workedexample``
environment defined in ``config.tex`` (chapter-prefixed counter via
``\\theworkedexample``, ``\\subcase{}`` for the Problem/Solution
substructure, and ``\\label{wex:N.M}`` + ``\\Cref``/``\\cref`` support via
``\\crefname``/``\\Crefname``).

This script performs the structural conversion of a chapter file in place
and emits a companion CSV mapping prose references to the old manual
numbering (e.g. "Worked Example W7.3", "Worked example~7.3") onto
``\\Cref{wex:7.3}``. That CSV is intended as input to ``replace_from_csv.py``,
which performs the actual text substitution for in-prose references -- kept
as a separate pass so the generic replacer can be reused for other
relabeling tasks and so the reference fixes can be reviewed/edited before
being applied.

Follows the same ``--chapter``/``-c`` CLI convention and ``backup/``-folder
backup behaviour as ``replace_from_csv.py``.

Usage
-----
    python convert_workedexample.py --chapter 7
    python convert_workedexample.py -c 7

Operates on ``chapter07_T12.tex`` in the current directory (chapter number
zero-padded to two digits), in place.

Behaviour
---------
1. Back up ``chapter<NN>_T12.tex`` into ``backup/`` (timestamped) before
   touching it.
2. Read the file.
3. Locate every ``\\begin{workedex}{...} ... \\end{workedex}`` block using
   brace-aware parsing of the environment's mandatory title argument (so
   nested braces, e.g. inline math in the title, are handled correctly).
   ``workedex`` environments are assumed not to nest.
4. Parse the title against ``Worked [Ee]xample W?N.M: <rest>``. Blocks whose
   title does not match this pattern are left untouched and reported as
   warnings (so they can be handled manually).
5. Within each matched block:
   - ``\\textbf{Problem:}`` or ``\\textbf{Problem}``   -> ``\\subcase{Problem}``
   - ``\\textbf{Solution:}`` or ``\\textbf{Solution}`` -> ``\\subcase{Solution}``
     (the source is inconsistent about the trailing colon; both forms are
     handled)
   - ``\\begin{workedex}{Worked example WN.M: <rest>}`` ->
     ``\\begin{workedexample}{<rest>}`` followed by ``\\label{wex:N.M}``
   - ``\\end{workedex}`` -> ``\\end{workedexample}``
6. For each converted example N.M, generate CSV rows mapping the eight
   standard prose-reference phrasings (case of "example", presence of "W",
   space vs. ``~`` before the number) to ``\\Cref{wex:N.M}``.
7. Write the converted file back to ``chapter<NN>_T12.tex`` and write the
   CSV to ``chapter<NN>_T12_workedexamples.csv``.

Key paths
---------
- Input/output: ``chapter<NN>_T12.tex`` in the current directory (in place)
- Backup: ``backup/chapter<NN>_T12_<timestamp>.tex``
- CSV: ``chapter<NN>_T12_workedexamples.csv``

Dependencies
------------
Standard library only (``re``, ``csv``, ``argparse``, ``pathlib``,
``shutil``, ``datetime``).

Notes
-----
- Only the eight *standard* reference phrasings are generated:
  {"Worked Example", "Worked example"} x {"W7.3", "7.3"} x
  {space, "~"} before the number. Any non-standard prose reference (e.g.
  "see W7.3 above") will not be covered and must be added to the CSV
  manually before running ``replace_from_csv.py``.
- The generated ``\\label{wex:N.M}`` is placed on its own line immediately
  after ``\\begin{workedexample}{...}``, before the (typically blank-line
  separated) body.
"""

import argparse
import csv
import re
import shutil
from datetime import datetime
from pathlib import Path

BEGIN = r"\begin{workedex}"
END = r"\end{workedex}"

TITLE_RE = re.compile(
    r"^\s*Worked\s+[Ee]xample\s+W?(\d+)\.(\d+)\s*:\s*(.*?)\s*$",
    re.DOTALL,
)


def backup_file(src):
    bkp_folder = src.parent / "backup"
    bkp_folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = bkp_folder / src.with_name(src.stem + "_" + ts + src.suffix)
    shutil.copy(src, backup)


def extract_braced_arg(text, brace_index):
    """Return (content, index_after_closing_brace) for the brace group
    starting at text[brace_index] == '{', handling nested braces."""
    if text[brace_index] != "{":
        raise ValueError(f'Expected "{{" at position {brace_index}')
    depth = 0
    i = brace_index
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace_index + 1 : i], i + 1
        i += 1
    raise ValueError("Unbalanced braces in environment argument")


def reference_variants(chapter, example):
    """All standard prose-reference phrasings for Worked Example chapter.example,
    mapped to the new \\Cref call."""
    num = f"{chapter}.{example}"
    target = f"\\Cref{{wex:{num}}}"
    variants = {}
    for word in ("Example", "example"):
        for w in ("W", ""):
            for sep in (" ", "~"):
                old = f"Worked {word}{sep}{w}{num}"
                variants[old] = target
    return variants


def convert(text):
    """Convert all workedex blocks in `text`.

    Returns (new_text, csv_rows, warnings, n_converted).
    """
    out = []
    csv_rows = {}
    warnings = []
    pos = 0
    n_converted = 0

    while True:
        start = text.find(BEGIN, pos)
        if start == -1:
            out.append(text[pos:])
            break
        out.append(text[pos:start])

        brace_start = start + len(BEGIN)
        if brace_start >= len(text) or text[brace_start] != "{":
            warnings.append(
                f"Malformed \\begin{{workedex}} at offset {start} "
                f"(no title argument); left as-is"
            )
            out.append(text[start:brace_start])
            pos = brace_start
            continue

        title, after_title = extract_braced_arg(text, brace_start)

        end = text.find(END, after_title)
        if end == -1:
            warnings.append(
                f"Unmatched \\begin{{workedex}} at offset {start} "
                f"(no \\end{{workedex}} found); left as-is"
            )
            out.append(text[start:after_title])
            pos = after_title
            continue

        body = text[after_title:end]

        m = TITLE_RE.match(title)
        if not m:
            warnings.append(
                f'Title does not match "Worked example WN.M: ..." pattern, '
                f"left as-is: {title!r}"
            )
            out.append(text[start : end + len(END)])
            pos = end + len(END)
            continue

        chapter, example, rest_title = m.groups()
        num = f"{chapter}.{example}"

        new_body = body
        new_body = re.sub(r"\\textbf\{Problem:?\}", r"\\subcase{Problem}", new_body)
        new_body = re.sub(r"\\textbf\{Solution:?\}", r"\\subcase{Solution}", new_body)

        new_block = (
            f"\\begin{{workedexample}}{{{rest_title}}}\n"
            f"\\label{{wex:{num}}}"
            f"{new_body}"
            f"\\end{{workedexample}}"
        )
        out.append(new_block)
        n_converted += 1

        csv_rows.update(reference_variants(chapter, example))

        pos = end + len(END)

    return "".join(out), csv_rows, warnings, n_converted


def main():
    parser = argparse.ArgumentParser(
        description="Convert workedex environments to workedexample, and emit a "
        "CSV of prose-reference replacements."
    )
    parser.add_argument("--chapter", "-c", type=int, help="chapter number")
    args = parser.parse_args()

    c = str(args.chapter).zfill(2)
    c_t12 = f"chapter{c}_T12.tex"
    input_file = Path(c_t12)

    backup_file(input_file)

    text = input_file.read_text(encoding="utf-8")
    new_text, csv_rows, warnings, n_converted = convert(text)

    output = input_file
    csv_path = input_file.with_name(f"{input_file.stem}_workedexamples.csv")

    print(
        f"[convert] {input_file.name}: {n_converted} workedex block(s) converted, "
        f"{len(csv_rows)} reference variant(s) generated"
    )
    for w in warnings:
        print(f"  WARNING: {w}")

    output.write_text(new_text, encoding="utf-8")
    print(f"[convert] Wrote to {output.name}")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["old", "new"])
        for old, new in sorted(csv_rows.items(), key=lambda kv: -len(kv[0])):
            writer.writerow([old, new])
    print(f"[convert] Wrote {csv_path.name} ({len(csv_rows)} rows)")


if __name__ == "__main__":
    main()
