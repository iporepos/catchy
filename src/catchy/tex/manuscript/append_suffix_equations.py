#!/usr/bin/env python3
"""Append a frozen-snapshot version suffix to Tier 1 equation labels.

Architectural context
----------------------
Part of the Tier 1 -> Tier 2 LaTeX conversion pipeline for "Catchment
Hydrology: An Integrated Treatment Across Scales". Tier 1 chapters use
positional equation keys of the form ``eq:N.M`` (chapter.equation-within-
chapter), assigned via ``\\label{eq:N.M}`` and referenced via ``\\ref{eq:N.M}``
or ``\\eqref{eq:N.M}``. These keys mirror the source document's own
equation numbering and are explicitly *not* semantic labels -- they are
disposable positional placeholders, as documented in
``Detailed_Instructions_for_Tier_1.md``.

At Tier 2, full semantic relabeling (``eq:budyko-aridity-index``, etc.) is
reserved for equations that warrant individual interpretation. For the bulk
of equations -- often 40+ per chapter -- this script applies a cheaper,
purely mechanical convention instead: freeze the existing positional key by
appending a version suffix (``-v2026.06``), signalling to authors that the
number is a snapshot of where the equation stood at this conversion pass,
not a live, renumbering-safe reference. This is the equation-label
counterpart to the ``label=keyname`` rule already adopted for ``tcolorbox``
environments: an explicit, non-magical key rather than reliance on
automatic counters.

Idempotent by construction: the matching pattern requires each key to end
immediately in ``\\d+\\.\\d+`` (optionally followed by more comma-separated
keys, but never by a hyphen), so a key already carrying the suffix
(``eq:2.7-v2026.06``) will not match again on a second run.

Follows the same ``--chapter``/``-c`` CLI convention and ``backup/``-folder
backup behaviour as ``convert_workedexample.py`` / ``replace_from_csv.py``.

Usage
-----
    python suffix_eq_labels.py --chapter 7
    python suffix_eq_labels.py -c 7
    python suffix_eq_labels.py -c 7 --suffix -v2026.07   # override default suffix
    python suffix_eq_labels.py -c 7 --dry-run            # report counts, no write

Operates on ``chapter<NN>_T12.tex`` in the current directory (chapter number
zero-padded to two digits), in place.

Behaviour
---------
1. Back up ``chapter<NN>_T12.tex`` into ``backup/`` (timestamped) before
   touching it.
2. Read the file.
3. Handle four reference shapes, each requiring different brace-content
   parsing:
   - Single-key commands: ``\\label{eq:N.M}``, ``\\ref{eq:N.M}``,
     ``\\eqref{eq:N.M}``, ``\\Cref{eq:N.M}``, ``\\cref{eq:N.M}`` -- one key
     per brace group.
   - Multi-key list commands: ``\\Cref{eq:N.M,eq:N.M,...}``,
     ``\\cref{eq:N.M,eq:N.M,...}`` -- comma-separated keys inside a single
     brace group; every key in the list is suffixed independently.
   - Range commands: ``\\crefrange{eq:N.M}{eq:N.M}``,
     ``\\Crefrange{eq:N.M}{eq:N.M}`` -- two separate brace groups (start key,
     end key), both suffixed.
4. Append the version suffix to every matched ``eq:N.M`` key, regardless of
   which command or position it appears in.
5. Report unique label keys, unique referenced keys (across all four
   shapes), and any referenced key with no matching ``\\label`` in this
   file (a dangling reference -- these are the ``??`` candidates at compile
   time, since a label and its references must carry an identical key
   after suffixing).
6. Write the converted file back to ``chapter<NN>_T12.tex``.

Key paths
---------
- Input/output: ``chapter<NN>_T12.tex`` in the current directory (in place)
- Backup: ``backup/chapter<NN>_T12_<timestamp>.tex``

Dependencies
------------
Standard library only (``re``, ``argparse``, ``collections``, ``pathlib``,
``shutil``, ``datetime``).

Notes
-----
- Only bare ``eq:N.M`` keys are matched (digits on both sides of a single
  dot). Keys already semantically relabeled (``eq:budyko-aridity-index``)
  are untouched, since they don't match the ``\\d+\\.\\d+`` pattern -- this
  script and manual semantic relabeling can be interleaved across a
  chapter without collision.
- ``\\crefrange``/``\\Crefrange`` are matched as two consecutive
  ``{eq:N.M}`` groups immediately following the command name. If a range
  command is ever used with anything other than two bare single-key
  groups (e.g. with an optional star or extra argument), it will not match
  and will be left untouched -- check warnings/dry-run output for such
  cases.
- Dangling-reference detection (refs with no matching label in this file)
  is a warning, not a hard failure -- some chapters may legitimately
  reference equations defined in a different chapter file. A genuinely
  cross-file reference will still show ``??`` after suffixing unless the
  other file's matching ``\\label`` is suffixed identically -- run this
  script consistently across all chapter files sharing labels.
- A stale ``.aux`` file can produce a spurious round of ``??`` on the
  first compile after suffixing even when labels/refs are now consistent;
  recompile twice (or delete the ``.aux``) before treating ``??`` as a
  real mismatch.
"""

import argparse
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

# EQ_KEY = r'eq:\d+\.\d+'
EQ_KEY = r'eq:\d+\.\d+[a-d]?'

# Single-key commands: one eq:N.M per brace group.
SINGLE_RE = re.compile(
    rf'\\(label|ref|eqref|Cref|cref)\{{({EQ_KEY})\}}'
)

# Multi-key list commands: \Cref{eq:N.M,eq:N.M,...} / \cref{...}
# (only matches when the brace group contains a comma; otherwise it's
# already covered by SINGLE_RE above)
LIST_RE = re.compile(
    rf'\\(Cref|cref)\{{((?:{EQ_KEY},)+{EQ_KEY})\}}'
)

# Range commands: \crefrange{eq:N.M}{eq:N.M} / \Crefrange{...}{...}
RANGE_RE = re.compile(
    rf'\\(crefrange|Crefrange)\{{({EQ_KEY})\}}\{{({EQ_KEY})\}}'
)

KEY_BARE_RE = re.compile(rf'^{EQ_KEY}$')

# Plain-text equation references: "Equation~1.8" or "Equation~1.8a"
PLAIN_RE = re.compile(
    r'(Equation~)(\d+\.\d+[a-d]?)'
)

def backup_file(src):
    bkp_folder = src.parent / "backup"
    bkp_folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    backup = bkp_folder / src.with_name(src.stem + '_' + ts + src.suffix)
    shutil.copy(src, backup)


def collect_keys(text):
    label_keys = set()
    ref_keys = Counter()

    for cmd, key in SINGLE_RE.findall(text):
        if cmd == 'label':
            label_keys.add(key)
        else:
            ref_keys[key] += 1

    for cmd, key_list in LIST_RE.findall(text):
        for key in key_list.split(','):
            ref_keys[key] += 1

    for cmd, start_key, end_key in RANGE_RE.findall(text):
        ref_keys[start_key] += 1
        ref_keys[end_key] += 1

    for _, number in PLAIN_RE.findall(text):
        ref_keys[f'eq:{number}'] += 1   # normalise to eq: key for cross-checking

    return label_keys, ref_keys


def apply_suffix(text, suffix):
    """Append `suffix` to every eq:N.M key across all four reference shapes."""

    def single_repl(m):
        return f'\\{m.group(1)}{{{m.group(2)}{suffix}}}'

    def list_repl(m):
        keys = m.group(2).split(',')
        suffixed = ','.join(k + suffix for k in keys)
        return f'\\{m.group(1)}{{{suffixed}}}'

    def range_repl(m):
        return f'\\{m.group(1)}{{{m.group(2)}{suffix}}}{{{m.group(3)}{suffix}}}'

    # Keep the word "Equation" before the cross-reference
    def plain_repl(m):
        return f'Equation~\\eqref{{eq:{m.group(2)}{suffix}}}'

    text = RANGE_RE.sub(range_repl, text)
    text = LIST_RE.sub(list_repl, text)
    text = SINGLE_RE.sub(single_repl, text)
    text = PLAIN_RE.sub(plain_repl, text)
    return text


def main():
    parser = argparse.ArgumentParser(
        description='Append a frozen-snapshot version suffix to eq:N.M labels, '
                    'refs, eqrefs, Cref lists, and crefrange pairs.'
    )
    parser.add_argument('--chapter', '-c', type=int, required=True, help='chapter number')
    parser.add_argument('--suffix', default='.v202601', help='suffix to append (default: -v2026.06)')
    parser.add_argument('--dry-run', action='store_true', help='report counts without writing')
    args = parser.parse_args()

    c = str(args.chapter).zfill(2)
    input_file = Path(f"chapter{c}_T12.tex")

    text = input_file.read_text(encoding='utf-8')
    label_keys, ref_keys = collect_keys(text)
    dangling_refs = sorted(k for k in ref_keys if k not in label_keys)

    n_labels = len(label_keys)
    n_ref_occurrences = sum(ref_keys.values())
    n_unique_refs = len(ref_keys)

    print(f'[suffix] {input_file.name}: {n_labels} unique label(s), '
          f'{n_ref_occurrences} ref occurrence(s) across {n_unique_refs} unique key(s)')

    if dangling_refs:
        print(f'  WARNING: {len(dangling_refs)} key(s) referenced but never labelled in this file:')
        for k in dangling_refs:
            print(f'    {k} (referenced {ref_keys[k]}x)')

    new_text = apply_suffix(text, args.suffix)

    if args.dry_run:
        print('[suffix] Dry run -- no changes written.')
        return

    backup_file(input_file)
    input_file.write_text(new_text, encoding='utf-8')
    print(f'[suffix] Wrote to {input_file.name}')


if __name__ == '__main__':
    main()