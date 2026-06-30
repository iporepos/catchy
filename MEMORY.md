# MEMORY

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
