#!/usr/bin/env python3
"""Generic literal string replacement engine driven by a CSV mapping.

Architectural context
----------------------
General-purpose companion to the chapter-specific conversion scripts in the
Tier 1 -> Tier 2 LaTeX pipeline (e.g. ``convert_workedexample.py``). Those
scripts emit a CSV of ``old``/``new`` string pairs for prose changes that
are easiest to express as plain find-and-replace (cross-references,
relabeling, terminology updates, etc.); this script applies that CSV to a
``.tex`` file. It has no knowledge of LaTeX syntax -- it treats the file as
plain text -- so it is reusable across many conversion tasks, not just the
worked-example relabeling.

Usage
-----
    python replace_from_csv.py chapter07_T2.tex chapter07_T1_wex_refs.csv
    python replace_from_csv.py chapter07_T2.tex chapter07_T1_wex_refs.csv -w
    python replace_from_csv.py chapter07_T2.tex refs.csv -o chapter07_T2_fixed.tex -w

Behaviour
---------
1. Read the CSV (must have ``old`` and ``new`` columns; any other columns
   are ignored).
2. Sort rows by length of ``old`` descending, so longer/more specific
   matches are applied before shorter ones that might otherwise match as a
   substring of them.
3. For each row, count occurrences of ``old`` in the text and replace all
   of them with ``new`` (literal substring replacement, not regex).
4. Report, per row, how many replacements were made. Rows with zero matches
   are reported as warnings (likely a stale CSV entry or a typo). Rows with
   an empty ``old`` value are skipped with a warning (an empty-string
   ``str.replace`` would match at every position).
5. By default this is a dry run (no files written, report only). Pass
   ``-w``/``--write`` to write for real. If the output path already exists,
   it is backed up with a timestamp suffix before being overwritten.

Key paths
---------
- Input: any ``.tex`` (or plain text) file
- CSV: two columns, ``old`` and ``new``
- Output: default is the input path (in place, with backup); override with
  ``-o``/``--output``

Dependencies
------------
Standard library only (``csv``, ``argparse``, ``pathlib``, ``shutil``,
``datetime``). Replacement is literal (``str.replace``), not regex, so CSV
entries do not need escaping.

Notes
-----
- Because replacement is purely literal and sequential, a CSV entry whose
  ``new`` value happens to contain another entry's ``old`` value as a
  substring can be re-matched by a later row. This is rarely an issue for
  LaTeX macro replacements (e.g. ``\\Cref{wex:7.3}``) but is worth keeping
  in mind when reusing this script for other CSVs.
"""

import argparse
import csv
import shutil
from datetime import datetime
from pathlib import Path


def backup_file(src):
    bkp_folder = src.parent / "backup"
    bkp_folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = bkp_folder / src.with_name(src.stem + "_" + ts + src.suffix)
    shutil.copy(src, backup)
    print("[BACKUP] Backup file saved to {}".format(backup))


def load_rows(csv_path):
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if (
            reader.fieldnames is None
            or "old" not in reader.fieldnames
            or "new" not in reader.fieldnames
        ):
            raise ValueError(
                f'{csv_path} must have "old" and "new" columns, found {reader.fieldnames}'
            )
        for row in reader:
            rows.append((row["old"], row["new"]))
    return rows


def apply_replacements(text, rows):
    """Apply (old, new) pairs to text, longest `old` first. Returns (new_text, report)."""
    ordered = sorted(rows, key=lambda r: -len(r[0]))
    report = []
    for old, new in ordered:
        if not old:
            report.append((old, new, None))
            continue
        count = text.count(old)
        if count:
            text = text.replace(old, new)
        report.append((old, new, count))
    return text, report


def main():
    parser = argparse.ArgumentParser(
        description="Apply old->new literal string replacements from a CSV to a text file."
    )
    parser.add_argument("--chapter", "-c", type=int, help="chapter number")
    parser.add_argument("--csv", type=Path, help='CSV with "old" and "new" columns')
    args = parser.parse_args()

    c = str(args.chapter).zfill(2)
    c_t12 = f"chapter{c}_T12.tex"
    input_file = Path(c_t12)

    backup_file(input_file)

    text = input_file.read_text(encoding="utf-8")
    rows = load_rows(args.csv)
    new_text, report = apply_replacements(text, rows)

    output = input_file

    total = 0
    for old, new, count in report:
        if old == "":
            print(f'  SKIPPED (empty "old") -> {new!r}')
            continue
        if count == 0:
            print(f"  WARNING: 0 matches for {old!r}")
        else:
            print(f"  {count:3d}x  {old!r} -> {new!r}")
        total += count or 0

    print(
        f"[replacer] {input_file.name}: {total} total replacement(s) across {len(rows)} CSV row(s)"
    )

    output.write_text(new_text, encoding="utf-8")
    print(f"[replacer] Wrote to {output.name}")


if __name__ == "__main__":
    main()
