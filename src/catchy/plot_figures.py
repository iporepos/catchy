"""
ScriptPlotFigures — Data-Based Figure Renderer
===============================================

Reads a JSON spec file and renders data-based figures using the plot-type
registry from :mod:`catchy.plots`. Supports filtering by chapter or by a
single figure name.

Architectural context
---------------------
Bridges :mod:`catchy.core` (``Script`` base class, path constants) and the
:mod:`catchy.plots` / :mod:`catchy.views` plotting stack. Reads
``HERE / "data" / "specs.json"`` (shipped with the repository), resolves the
registered :class:`~catchy.views.Plotter` subclass for each entry, and drives
the full render pipeline.

Spec file structure
-------------------
``HERE / "data" / "specs.json"`` must use chapter keys as the top-level grouping::

    {
      "chapter01": {
        "C01-mtx-georgia-a": { "class": "time-series", "data": [...], ... },
        "C01-mtx-rainfall":  { "class": "time-series", ... }
      },
      "chapter02": {
        "C02-mtx-streamflow": { ... }
      }
    }

Chapter keys must follow the ``chapter<NN>`` format with a leading zero.

Usage
-----
Run directly::

    python plot_figures.py                                  # all chapters, all figures
    python plot_figures.py --chapter 1                      # all figures in chapter01
    python plot_figures.py --chapter all -w                 # write mode, all figures
    python plot_figures.py --figure C01-mtx-georgia-a -w   # single figure, write mode

Arguments
---------
    --chapter   Chapter number to process, or ``all`` for the full range.
                Ignored when ``--figure`` is provided.
    --figure    Exact figure name (e.g. ``C01-mtx-georgia-a``). Chapter is
                derived automatically from the name prefix.
    -w          Write mode. Without it, each figure is rendered and displayed
                via ``plt.show()`` instead of being saved to disk.

Behaviour
---------
For each figure to be processed:

1. Load ``HERE / "data" / "specs.json"`` and resolve the ``chapter<NN>`` block.
2. Apply figure filter if ``--figure`` was given.
3. Instantiate the registered plot class via :func:`~catchy.plots.get_plot_class`.
4. Set ``plot.write`` from the Script write gate.
5. Call ``plot.run()``.
6. **Safe mode** (no ``-w``): call ``plt.show()`` then ``plt.close()`` — renders
   interactively without writing any file.
7. **Write mode** (``-w``): ``plot.run()`` saves the file and closes the figure.

Key paths
---------
    Spec file:   HERE / "data" / "specs.json"  (shipped with the repository)
    Output root: FIGURES_DIR / <chapter> / "plots"  (resolved from chapter key; created on first write)

Dependencies
------------
    catchy.core     Script, DATA_DIR, LOG_PREFIX, and all core constants
    catchy.views    load_spec
    catchy.plots    get_plot_class
    matplotlib      pyplot (show / close in safe mode)

Notes
-----
    - When ``--figure`` is given, ``--chapter`` is ignored; the chapter is
      derived from the figure name prefix (e.g. ``C01`` → ``chapter01``).
    - When neither ``--chapter`` nor ``--figure`` is given, all chapters in
      the spec file are processed.
    - Safe mode shows one window per figure; each must be closed before the
      next is displayed.
    - ``plot.show`` is always set to ``False`` inside this script so that
      ``viewer.ship_fig`` never triggers a display call — ``plt.show()`` is
      called explicitly here instead.
"""

import matplotlib.pyplot as plt

from catchy.core import *
from catchy.views import load_spec
from catchy.plots import get_plot_class


class ScriptPlotFigures(Script):
    TITLE = "PLOT DATA FIGURES"
    LOG_NAME = LOG_PREFIX.format("plot-figures")

    SPEC_FILE = HERE / "data" / "specs.json"

    def __init__(self):
        super().__init__()
        self.figure = None

    def get_parser(self):
        parser = super().get_parser()
        parser.add_argument(
            "--figure",
            default=None,
            help="Exact figure name, e.g. C01-mtx-georgia-a",
        )
        return parser

    def set_arguments(self, args):
        super().set_arguments(args)
        self.figure = args.figure

    def run(self):
        self.print_heading("=")
        print(self.TITLE)

        args = self.get_arguments()
        self.set_arguments(args=args)

        self.handle_mode(self.write)

        if self.figure is not None:
            # derive chapter from figure name prefix: "C01-..." → 1
            c_n = int(self.figure.split("-")[0][1:])
            chapters = [c_n]
        elif args.chapter is not None:
            chapters = self.handle_chapter(args.chapter)
        else:
            chapters = self.handle_chapter("all")

        for chapter in chapters:
            self.print_chap(chapter)
            self.current_chapter = chapter
            self.print_step("Starting processing")
            self.processing()

        self.print_step("Done")

    def processing(self):

        if not self.SPEC_FILE.exists():
            self.print_warn(f"Spec file not found: {self.SPEC_FILE}")
            return None

        dc = load_spec(self.SPEC_FILE)

        chn = self.get_chapter_folder_name(self.current_chapter)
        chapter_specs = dc.get(chn, None)

        if chapter_specs is None:
            self.print_warn(f"No specs found for {chn}")
            return None

        if self.figure is not None:
            if self.figure not in chapter_specs:
                self.print_warn(f"Figure '{self.figure}' not found in {chn}")
                return None
            figures = {self.figure: chapter_specs[self.figure]}
        else:
            figures = chapter_specs

        self.print_info(f"{chn} — {len(figures)} figure(s) to process")

        for name, spec in figures.items():
            self.print_step(f"plotting {name}")

            cls = get_plot_class(spec["class"])
            plot = cls(name, spec)
            plot.data_dir = DATA_DIR / "plots" / chn
            plot.output_root = FIGURES_DIR / chn / "plots"
            plot.write = self.write
            plot.show = False

            plot.run()

            if not self.write:
                plt.show()
                plt.close(plot.fig)

        return None


if __name__ == "__main__":

    s = ScriptPlotFigures()
    s.run()
