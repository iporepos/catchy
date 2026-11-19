# MEMORY

## 2026-06-30 (SVG export docs)

- Updated docs in `views.py` and `plot_figures.py` to cover SVG export feature.
  - `Plotter._save_figure`: added docstring — writes two files: raster (`self.suffix`, default `jpeg`) + companion `.svg` at the same path.
  - `Plotter._setup_fig`: docstring updated — notes that `svg.fonttype = 'none'` is set so SVG fonts render as editable text, not paths.
  - `Plotter` class docstring: "Saving" bullet updated to mention raster + SVG.
  - Module header (`views.py`): `Plotter` description and Notes section updated with dual-output and SVG fonttype details.
  - `plot_figures.py` header: "Key paths" extended with output file line (`<name>.jpeg + <name>.svg`); step 7 in Behaviour updated to say "saves both a JPEG and a companion SVG".

## 2026-06-30 (continued)

- Added header docstrings to all 14 modules. Replaced `"""Head docs"""` placeholders in
  `reformat_svg_flags.py` and `reformat_svg_sizes.py`. Added missing module docstrings to
  `views.py`, `plots.py`, `bench1.py`. Upgraded thin docstring in `core.py` with full
  constants list, Script description, and import-time behaviour notes.

- Added `plot_figures.py` — new `ScriptPlotFigures(Script)` for data-based figure rendering.
  - Args: `--chapter N|all`, `--figure C01-mtx-name`, `-w`.
  - Safe mode (no `-w`): renders and calls `plt.show()` per figure instead of saving.
  - Write mode (`-w`): saves via `Plotter._save_figure()`, no display.
  - Spec file: `HERE / "data" / "specs.json"` (shipped with repo, not the external DATA_DIR).
  - Per-plotter overrides set in `processing()` before `plot.run()`:
    - `plot.data_dir    = DATA_DIR / "plots" / chn`  (external project CSV data)
    - `plot.output_root = FIGURES_DIR / chn / "plots"` (created automatically on first write)
    - `plot.show = False` (show is controlled explicitly, not via ship_fig)

- Restructured `data/specs.json`: added `chapter<NN>` top-level key grouping; removed
  redundant `chapter01/` prefix from all `"path"` entries — chapter resolved from hierarchy
  key in `plot_figures.py`.

## 2026-06-30

- Analysed full structure of `src/catchy/` (14 modules): pipeline order, dependencies, and module roles documented.
- Classified all scripts for idempotency: `setup_svg` is intentionally one-pass (overwrites SVGs for stand-by notes unconditionally, write-gate does not apply). `publish_src` and `publish_main` have no safe mode. All others are safe to re-run.
- Upgraded `README.md` with: overview, pipeline execution order, general warnings, CLI conventions, and a per-module micro reference (intent, run command, re-run safety, caveats).
- Notable bug flagged: `reformat_svg_sizes.py` class is named `ScriptReformatFonts` (copy-paste artifact, should be `ScriptReformatSizes`).

## 2026-09-11 (graceful error handling in build_figures)

- Added per-figure `try/except Exception` in `ScriptBuildFigures.processing()` (`src/catchy/build_figures.py`).
  - The batch loop no longer aborts on a bad SVG — failures are caught, the loop continues.
  - Two warning summaries printed at the end of each run:
    1. Figures skipped via `SKIP_FIGS` hard-coded list.
    2. Figures that failed to build, each with its error message.
  - `send_to_drive()` still runs after the loop, distributing whatever was successfully built.

## 2026-09-11 (move SKIP_FIGS to config.local.json)

- Removed hardcoded `SKIP_FIGS` class variable from `ScriptBuildFigures` in `src/catchy/build_figures.py`.
- Added `"skip_figs"` key to `config.local.json` (project root) with the same list.
- Skip check in `processing()` now reads `config.get("skip_figs", [])` — `config` is already in scope via `from catchy.core import *`.
- The `.get(..., [])` fallback makes the key optional in the JSON.

## 2026-11-04 07:38 (--recent flag and built-only distribution in build_figures)

- Added `--recent [HOURS]` to `ScriptBuildFigures` in `src/catchy/build_figures.py` (default `RECENT_HOURS = 24`, accepts decimals).
  - Selects figures with `status != 'stand-by'` whose paired SVG modification time is inside the window. This replaces the default `concluded`/`pending` filter for that run.
  - Ignored when `--figure` is set. Figures in `skip_figs` are still skipped.
  - When nothing matches, warns and stops before rendering or distribution.
- `send_to_drive()` now takes optional `ls_names`; `None` keeps the old send-everything behavior.
- `processing()` passes the figures built in the current run, on all runs. Older files in `STD_OUTPUT` and output from figures that failed partway are no longer copied.

## 2026-11-11 15:09 (lint_purge_authornotes script)

- Added `src/catchy/tex/manuscript/lint_purge_authornotes.py`: removes every `\authornote{...}` call (macro from `config_manuscript.tex`) from a `.tex` file.
  - CLI: positional file path, optional `-o/--output`. In-place runs back up to `backup/` next to the file; `-o` runs take no backup.
  - Brace-counting parser: nested groups and multi-line notes removed whole; `\authornote` definition, `\authornotes`, notes inside `%` comments, and escaped braces are left alone.
  - Whitespace: whole-line notes drop the line (and one of two resulting consecutive blanks); inline notes drop following spaces, or preceding spaces when followed by punctuation/EOL.
  - Line endings (LF/CRLF) preserved via `newline=''`. Unbalanced braces raise `ValueError` before anything is written.
  - `backup_file()` uses `bkp_folder / (stem + ts + suffix)`. The version in `lint_purge_decorations.py` (`bkp_folder / src.with_name(...)`) puts the backup next to the file instead of in `backup/` when given an absolute path; that file was not changed.

## 2026-11-17 06:05 (fixed-width tqdm progress bars)

- Added `PBAR_FORMAT = "{l_bar}{bar:50}{r_bar}"` to `src/catchy/core.py` (constants block, after `LOG_PREFIX`).
  - Keeps tqdm's default left/right text, but the bar itself is always 50 characters, regardless of terminal width.
- Passed `bar_format=PBAR_FORMAT` to every active `tqdm(...)` call (19 calls): `build_figures.py`, `build_catalog.py`, `reformat_svg_flags.py`, `reformat_svg_fonts.py`, `reformat_svg_sizes.py`, `setup_svg.py`, `standardize_svg.py`, `update_notes.py`.
  - The constant reaches each module via the existing `from catchy.core import *`.
  - The commented-out tqdm loop in `reformat_svg_flags.py` was left as is.

## 2026-11-17 08:01 (batch-aware write gate in build_figures)

- `ScriptBuildFigures` (`src/catchy/build_figures.py`) now defers the write confirmation until the batch size is known.
  - New class constant `LARGE_BATCH = 3` and instance flag `write_confirmed`.
  - `handle_mode()` override: with `-w`, prints the WRITING MODE banner and sets `self.write = True` without prompting; safe mode delegates to `Script.handle_mode()` unchanged.
  - `processing()`: after filtering and printing the list, if `self.write` and `len(df) >= LARGE_BATCH` and not yet confirmed → `gate_keeper()`. Yes sets `write_confirmed` (no re-ask in later chapters); No sets `self.write = False` (safe mode for the rest of the run, as before).
  - Batch size is per chapter (`--chapter all` processes chapters one at a time).
- `core.py` untouched; other scripts keep the upfront prompt.
- README `build_figures` section: added a note on the batch-aware gate.

## 2026-11-18 10:20 (tolerate Inkscape crash-on-exit in build_figures)

- Cause found: Inkscape 1.2.2 writes the PDF in `FigureSVG.to_pdf` stage 2 (`_crop.svg` -> pdf), then crashes on exit with `0xC0000374` (exit 3221226356). `check=True` in `losalamos` raised, so the figure was marked failed, its JPEG was skipped, and nothing was sent to drive. Seen on `C06-mtx-force`; File > Clean Up Document did not help.
- `ScriptBuildFigures._tolerate_exit_crash(func, expected_outputs, **kwargs)` (staticmethod, `src/catchy/build_figures.py`):
  - Records `t0`, calls `func`. On `subprocess.CalledProcessError`, accepts the step only if every expected output exists, is non-empty, and has `st_mtime >= t0` (`t0` taken 2 s early: Windows file timestamps use a coarser clock than `time.time()`, a fresh file was rejected in testing without the margin); otherwise re-raises.
  - Returns a warning string when tolerated, else None.
- `processing()`: PDF step goes through the handler with expected output `STD_OUTPUT / "<fig>_T1.pdf"`; tolerated figures go into new `ls_tolerated` and still into `ls_built` (JPEG built, sent to drive). Summary prints them as "built despite a renderer crash on exit".
- JPEG/PNG steps unchanged (`to_image` does not use `check=True`). `losalamos` untouched.
- Module header and README `build_figures` section updated with a note.
