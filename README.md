# catchy

Python modules, scripts, and specs supporting scientific illustrations for a Hydrology Textbook.
Source lives in `src/catchy/` (src-layout convention).

---

## Overview

`catchy` is a figure management and publication pipeline. It takes Markdown note files (YAML
front-matter + body) and paired Inkscape SVG files as input, and produces rasterized figures,
LaTeX catalog documents, and published output folders.

The pipeline runs in stages. Each stage is a standalone script that reads from and writes to
a shared directory tree configured in `config.local.json`.

**Intended execution order:**

```
setup_svg          →  seed blank SVG templates for new figures
standardize_svg    →  normalize layer names, IDs, stroke widths
reformat_svg_fonts →  enforce uniform typography
reformat_svg_sizes →  fix layer transforms and frame pixel widths
reformat_svg_flags →  stamp a processing-complete marker on notes
build_figures      →  render SVG → JPEG / PNG / PDF
update_notes       →  sync YAML front-matter fields
build_catalog      →  generate per-chapter LaTeX catalog
publish_src        →  deploy source figure folders
publish_main       →  deploy main-text figure folders
```

**Data figure pipeline (independent track):**

```
plot_figures       →  render data-based figures from repo/data/specs.json
```

**Supporting infrastructure (not run directly):**

```
core.py            →  config constants, Script base class
views.py           →  Plotter base class (spec loading, CSV ingestion, figure save)
plots.py           →  PlotTimeSeries + plot-type registry
```

---

## General warnings

- **SVG files are mutated in-place.** There is no backup step in any script. Work under
  version control or take manual backups before bulk processing.
- **Write mode must be requested explicitly** with the `-w` flag. Without it, most scripts
  run in safe (dry-run) mode and touch no files. Exceptions are noted per-module below.
- **`setup_svg` overwrites SVGs unconditionally**, regardless of `-w`. Re-running it on a
  figure still in `stand-by` status will silently destroy any existing SVG edits for that note.
- **`publish_src` and `publish_main` have no safe mode.** They write immediately on execution.
- **Non-ASCII characters are stripped silently** by `build_catalog` when generating LaTeX
  output (captions, comments, credits). Author names with diacritics will be lost.

---

## CLI conventions

All `Script`-based modules share the same argument interface:

```bash
python <script>.py --chapter <N>      # process a single chapter
python <script>.py --chapter all      # iterate over all chapters (CHAPTER_START–CHAPTER_END)
python <script>.py --chapter <N> -w   # enable write mode (required to modify files)

# examples
python standardize_svg.py --chapter 3        # dry run on chapter 3
python standardize_svg.py --chapter 3 -w     # write mode on chapter 3
python standardize_svg.py --chapter all -w   # write mode over all chapters
```

Chapter range and directory paths are resolved from `config.local.json` at import time.

---

## Module reference

### `setup_svg`

Seeds blank SVG templates for figures in `stand-by` status. Copies `_chennai.svg` from the
templates folder alongside each matching note file, naming the copy after the note stem.
Think of this as an "initialize working file" tool — run it once per figure before starting
illustration work in Inkscape.

```bash
python setup_svg.py --chapter <N> [--collection <cover|main text|biography|box|all>] [-w]

# examples
python setup_svg.py --chapter 3                              # all collections, dry run
python setup_svg.py --chapter 3 --collection "main text"    # main text figures only
python setup_svg.py --chapter all --collection "box" -w     # box figures, all chapters
```

> [!CAUTION]
> **Re-run: one-pass per figure.** Re-running overwrites any existing SVG for notes still in `stand-by`, destroying edits. The `-w` flag does not prevent this — the copy runs unconditionally.

---

### `standardize_svg`

Normalizes all SVG files in a chapter: renames the `frame` layer to `frames`, renames the
`mainframe` element to the size identifier from note metadata (e.g. `single`, `double`), and
sets `stroke-width: 0.2` on all elements in the `frames` layer.

```bash
python standardize_svg.py --chapter <N> [-w]

# examples
python standardize_svg.py --chapter 3       # dry run
python standardize_svg.py --chapter 3 -w    # write mode
python standardize_svg.py --chapter all -w  # all chapters
```

> [!TIP]
> **Re-run: safe.** Layer rename is guarded (skipped if already done); stroke-width is always set to the same fixed value.

---

### `reformat_svg_fonts`

Applies the uniform font family `"Helvetica LT Std"` across all layers of every active SVG in
the chapter. Notes with `status == 'stand-by'` are skipped. Font availability is not validated
at runtime; missing fonts produce a silent fallback at export time.

```bash
python reformat_svg_fonts.py --chapter <N> [-w]

# examples
python reformat_svg_fonts.py --chapter 3       # dry run
python reformat_svg_fonts.py --chapter 3 -w    # write mode
python reformat_svg_fonts.py --chapter all -w  # all chapters
```

> [!TIP]
> **Re-run: safe.** Setting the same font family is idempotent.

---

### `reformat_svg_sizes`

Corrects layer matrix transforms (resets scale components to 1 while preserving translation)
and sets pixel widths on frame elements according to size codes: `L=172px`, `M=126px`,
`S=83.5px`. Targets active figures only (`status != 'stand-by'`).

```bash
python reformat_svg_sizes.py --chapter <N> [-w]

# examples
python reformat_svg_sizes.py --chapter 3       # dry run
python reformat_svg_sizes.py --chapter 3 -w    # write mode
python reformat_svg_sizes.py --chapter all -w  # all chapters
```

> [!TIP]
> **Re-run: safe.** Scale fix has an early-exit guard if already correct; width values are fixed constants.

> Note: the class inside this file is named `ScriptReformatFonts` — copy-paste artifact.
> The correct name should be `ScriptReformatSizes`.

---

### `reformat_svg_flags`

Appends a processing-complete marker string to the `comment` field of each active note's
YAML front-matter. Signals that the SVG has been through the reformat pipeline and is
ready for fine-tune adjustment.

```bash
python reformat_svg_flags.py --chapter <N> [-w]

# examples
python reformat_svg_flags.py --chapter 3       # dry run, inspect which notes would be flagged
python reformat_svg_flags.py --chapter 3 -w    # write mode
python reformat_svg_flags.py --chapter all -w  # all chapters
```

> [!TIP]
> **Re-run: safe.** Explicitly checks whether the flag string is already present and skips the note if so — the marker is never written twice.

---

### `build_figures`

Renders active SVG files (status `concluded` or containing `pending`) to raster output.
Produces JPEG and PDF for standard figures; PNG and PDF for `box` collection figures
(transparent background). Distributes all generated files to `FIGURES_DIR/chapter<NN>/T1/`.

```bash
python build_figures.py --chapter <N> [--collection <cover|main text|biography|box|all>] [-w]

# examples
python build_figures.py --chapter 3                              # dry run, all collections
python build_figures.py --chapter 3 -w                          # write mode, all collections
python build_figures.py --chapter 3 --collection "main text" -w # main text figures only
python build_figures.py --chapter 3 --collection box -w         # box figures (PNG output)
```

> [!WARNING]
> **Re-run: safe but expensive.** Re-renders and re-copies everything in scope each time. There is no skip-if-unchanged logic.

---

### `build_catalog`

Generates per-chapter LaTeX catalog documents from figure metadata. Produces one `.tex` entry
per figure (from a `_catalog_figure.tex` template with `[[placeholder]]` substitution), a
status-report table, and a merged chapter file. Also mirrors T0/T1 image files into the
catalog directory for standalone compilation.

`copy_figures_to_chapter` runs regardless of the `-w` flag — it copies already-published
image files and is not gated by write mode.

```bash
python build_catalog.py --chapter <N> [-w]

# examples
python build_catalog.py --chapter 3       # dry run (note: image copy still runs)
python build_catalog.py --chapter 3 -w    # write mode, generate all .tex files
python build_catalog.py --chapter all -w  # full catalog for all chapters
```

> [!TIP]
> **Re-run: safe.** All output files are written with overwrite mode; the chapter `.tex` is fully regenerated from current metadata on each run.

---

### `update_notes`

Synchronises YAML front-matter fields in figure note files with values derived
deterministically from existing metadata: tags, title (`Figure/Box/Biography <ch>.<order>`),
aliases, abstract (copied from caption into the note heading), and file link fields
(`[[name_T1.jpeg]]`, `[[name_T0.jpeg]]`).

```bash
python update_notes.py --chapter <N> [-w]

# examples
python update_notes.py --chapter 3       # dry run, inspect derived values
python update_notes.py --chapter 3 -w    # write mode
python update_notes.py --chapter all -w  # sync metadata across all chapters
```

> [!TIP]
> **Re-run: safe.** Every field is derived from the same source data — repeated runs produce identical output.

---

### `publish_src`

Batch-publishes all source figure chapter folders to the configured output location using
the `losalamos` publish pipeline. Uses `publish_force=True` (existing output files are
overwritten without prompting).

```bash
python publish_src.py   # always writes — no dry-run available
```

> [!WARNING]
> **Re-run: safe but no dry-run.** There is no `-w` gate — execution always writes immediately. Verify the output folder before running in sensitive environments.

---

### `publish_main`

Identical to `publish_src` in structure and behaviour, but targets the main-text figure tree
and uses `PREFIX_PUB_MAIN` instead of `PREFIX_PUB_SRC`.

```bash
python publish_main.py  # always writes — no dry-run available
```

> [!WARNING]
> **Re-run: safe but no dry-run.** Same caveat as `publish_src` — no safe mode available.

---

### `plot_figures`

Renders data-based figures using the plot-type registry from `plots.py`. Reads
`repo/data/specs.json` (shipped with the repository), which groups figure specs under
`chapter<NN>` keys. For each figure, instantiates the registered plotter, resolves data
paths from `DATA_DIR / "plots" / <chapter>`, and writes output to
`FIGURES_DIR / <chapter> / "plots"` (created automatically on first write).

This is an independent pipeline, separate from the SVG illustration workflow. Run it
whenever data-based figures need to be regenerated.

```bash
python plot_figures.py [--chapter <N>|all] [--figure <name>] [-w]

# examples
python plot_figures.py                                    # show all figures interactively
python plot_figures.py --chapter 1                        # show chapter 1 figures only
python plot_figures.py --chapter 1 -w                     # write mode, all chapter 1 figures
python plot_figures.py --figure C01-mtx-georgia-a -w      # single figure, write mode
python plot_figures.py --chapter all -w                   # write all chapters
```

> [!TIP]
> **Re-run: safe.** Write mode overwrites output files deterministically. Safe mode (no `-w`) renders each figure and opens it in an interactive window — no files are written. Each window must be closed before the next figure is displayed.

---

## Infrastructure modules

### `core`

Foundation for the entire library. Provides directory constants (`BASE_DIR`, `FIGURES_DIR`,
`DOCUMENTS_DIR`, `STD_OUTPUT`, etc.) resolved from `config.local.json`, and the `Script`
base class that all pipeline scripts subclass. `Script` supplies CLI argument parsing
(`--chapter`, `-w`), write-mode gating with a confirmation prompt, standard console logging,
and chapter iteration. Not run directly.

### `views`

Base `Plotter` class: loads a JSON spec file, ingests CSV data, sets up matplotlib figures
via the `plans` library, and handles save/close. Imported by `plots`. Not run directly.

### `plots`

`PlotTimeSeries` subclass of `Plotter` for date/year-based time-series rendering. Provides
a `@register_plot` decorator and a `PLOT_REGISTRY` dictionary for registering and retrieving
plot types by name. Not run directly.
