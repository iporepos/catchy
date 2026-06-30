"""
Plotter Base Infrastructure
============================

Base plotting infrastructure for the catchy figure pipeline. Provides the
:class:`Plotter` class, the :func:`load_spec` utility, and the module-level
:data:`FIG_SIZES` used by all concrete plot modules.

Architectural context
---------------------
Sits at the base of the plotting stack. :class:`Plotter` is subclassed by
:mod:`catchy.plots` (and any future plot-type modules). Imports
:data:`~catchy.core.DATA_DIR` and :data:`~catchy.core.FIGURES_DIR` from
:mod:`catchy.core` for path resolution; has no other internal dependencies.

The module applies a two-layer style strategy: ``plans.viewer`` supplies the
``wien`` style (colors, frame, grid), and catchy overrides figure sizes via
the local :data:`FIG_SIZES` dict and the font family via
:func:`_register_helvetica` + an ``rcParams`` override in
:meth:`Plotter._setup_fig`.

Key classes and functions
-------------------------
:class:`Plotter`
    Base plotter. Handles spec loading from a JSON file, CSV data ingestion
    via ``spec["data"]`` entries, figure setup through the ``plans.viewer``
    library (``build_fig`` / ``ship_fig``), and save/close orchestration.
    Subclasses override :meth:`Plotter._draw` to provide rendering logic.
    The default :meth:`_draw` implementation is a random-scatter stub.

:func:`load_spec`
    Reads a JSON spec file from disk and returns it as a :class:`dict`.

:func:`_register_helvetica`
    Scans the user-level Windows font directory for Helvetica font files and
    registers them with matplotlib's font manager. Called once on module
    import so that ``font.family = "Helvetica"`` resolves correctly even when
    the font is installed per-user rather than system-wide.

:data:`FIG_SIZES`
    Catchy-local figure size table (mm). Mirrors the key set of
    ``plans.viewer.FIG_SIZES`` but is edited here independently.

:data:`DC_COLORS`
    Module-level colour palette for standard variable types:
    ``"rain"`` and ``"streamflow"``.

Dependencies
------------
    catchy.core             DATA_DIR, FIGURES_DIR
    plans.viewer            build_fig, ship_fig
    matplotlib              pyplot, font_manager (figure lifecycle and font registration)
    pandas                  CSV ingestion and date handling
    numpy                   Random data used in the default _draw stub

Notes
-----
    - :meth:`Plotter._draw` must be overridden by subclasses to produce
      meaningful output; the stub draws random scatter data.
    - Output files are written to ``FIGURES_DIR / "raw"`` by default.
      Override ``output_root`` before calling :meth:`Plotter.run` to
      redirect output.
    - ``Plotter.write`` defaults to ``True``, unlike the CLI-driven
      ``Script`` subclasses where ``-w`` must be passed explicitly.
    - Font registration via :func:`_register_helvetica` only searches the
      per-user font path (``%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts``).
      System-wide Helvetica installations are already visible to matplotlib
      without explicit registration.
"""
from logging import setLogRecordFactory

from catchy.core import DATA_DIR, FIGURES_DIR
import json, os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from plans import viewer

FIG_SIZES = {
    "S":  {"w": 81,  "h": 80},
    "M":  {"w": 120, "h": 80},
    "M2": {"w": 120, "h": 60},
    "L":  {"w": 170, "h": 80},
    "L2": {"w": 170, "h": 60},
}
"""Catchy-local figure size table (mm). Edit here to tune sizes independently
of ``plans.viewer.FIG_SIZES``. Keys match those used in the spec ``"size"`` field."""

DC_COLORS = {"rain": "steelblue", "streamflow": "navy"}  # "#6d7fa2ff",  # "#223b85ff"

def _register_helvetica():
    """
    Register per-user Helvetica font files with matplotlib.

    Scans ``%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts`` and adds any file
    whose path contains ``"helv"`` (case-insensitive) to the font manager.
    Must be called before the first ``rcParams["font.family"]`` assignment
    that references Helvetica.
    """
    font_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts")
    for font_file in fm.findSystemFonts(fontpaths=[font_dir]):
        if "helv" in font_file.lower():
            fm.fontManager.addfont(font_file)

_register_helvetica()  # runs once on module import

def load_spec(spec_path):
    with open(spec_path, "r") as f:
        return json.load(f)


class Plotter:
    """
    Infrastructure-level plotter.
    Handles:
        - Spec loading
        - Data ingestion
        - Figure lifecycle
        - Saving / closing
    Delegates drawing to subclasses.
    """

    def __init__(self, name, spec_dict):
        self.name = name
        self.spec = spec_dict
        self.data_dir = DATA_DIR / "plots"
        self.output_root = FIGURES_DIR / "raw"
        self.output_file = None

        self.fig = None
        self.gs = None
        self.axes = None

        self.show = True
        self.is3d = False

        self.suffix = "jpeg"
        self.style = "wien"
        self.dpi = 600

        self.write = True

    # ----------------------------
    # Public API
    # ----------------------------

    def run(self) -> None:
        """
        Execute full plotting pipeline:
            1. Load data
            2. Create figure
            3. Delegate drawing
            4. Save
            5. Close
        """

        self._load_data()
        self._setup_fig()

        self._draw()

        if self.write:
            try:
                self._save_figure()
            finally:
                plt.close(self.fig)

    # ----------------------------
    # Internal Infrastructure
    # ----------------------------

    def _load_data(self):
        """
        Load all CSV files declared in spec["data"].
        Returns dict keyed by declared id.
        """
        data_dict = {}
        i = 0
        for entry in self.spec.get("data", []):
            data_id = i
            path = self.data_dir / Path(entry["path"])

            if not path.exists():
                raise FileNotFoundError(f"Data file not found: {path}")

            data_dict[data_id] = pd.read_csv(path, sep=entry.get("sep", ","))
            i = i + 1
        self.data = data_dict.copy()

    def _setup_fig(self):
        """
        Create the matplotlib figure and GridSpec.

        Calls ``plans.viewer.build_fig`` (which applies the wien style), then
        overrides the font family to Helvetica before axes are added so that
        all subsequent text elements use the catchy font.
        """
        specs = self.get_view_specs()
        # setup fig
        self.fig, self.gs = viewer.build_fig(specs=specs)
        # override font after wien style is applied
        plt.rcParams["font.family"] = "Helvetica"
        plt.rcParams['svg.fonttype'] = 'none'
        # add axes
        if self.is3d:
            self.fig.add_subplot(self.gs[:, :], projection="3d")
        else:
            self.fig.add_subplot(self.gs[:, :])
        # access axes
        self.axes = self.fig.get_axes()

    def _set_output_file(self):
        s = f"{self.name}.{self.suffix}"
        self.output_file = Path(self.output_root) / s

    def _save_figure(self):
        self._set_output_file()
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        # ship fig image
        # ----------------------------------------------------
        self.ship_fig(
            self.fig,
            show=self.show,
            file_output=str(self.output_file),
            dpi=self.dpi,
        )
        # ship fig svg
        # ----------------------------------------------------
        out_svg = self.output_file.with_suffix(".svg")
        self.ship_fig(
            self.fig,
            show=self.show,
            file_output=str(out_svg),
            dpi=self.dpi,
        )

    @staticmethod
    def ship_fig(fig, show=True, file_output=None, dpi=300):
        if show:
            plt.show()
            return None
        elif file_output is not None:
            fig.patch.set_visible(False)
            fig.savefig(file_output, dpi=dpi)
            plt.close(fig)
            return None
        else:
            return None

    # ----------------------------
    # To Be Implemented by Child
    # ----------------------------

    def _draw(self) -> None:
        """
        Subclasses must overwrite drawing logic.
        """
        # get data
        # ----------------------------------------------------
        x = np.random.normal(loc=100, scale=2, size=1000)
        y = np.random.normal(loc=100, scale=3, size=1000)

        # plot data
        # ----------------------------------------------------
        self.axes[0].scatter(x, y, marker=".", alpha=0.5, color="magenta")

        # fine tuning axe
        # ----------------------------------------------------
        self.axes[0].set_xlim(self.spec["data"][0]["xlim"])
        self.axes[0].set_ylim(self.spec["data"][0]["ylim"])

    def get_view_specs(self):
        """
        Build the spec dict consumed by ``plans.viewer.build_fig``.

        Width is read from the local :data:`FIG_SIZES` table using
        ``spec["size"]`` as the key. Height falls back to the table value when
        not supplied in the spec.
        """

        size = self.spec["size"]
        w = FIG_SIZES[size]["w"]

        h = self.spec.get("height", None)
        if h is None:
            h = FIG_SIZES[size]["h"]

        return {
            "style": self.style,
            "width": w,
            "height": h,
            "nrows": 1,
            "ncols": 1,
            "gs_wspace": 0.05,
            "gs_hspace": 0.05,
            "gs_left": self.spec.get("gs_left", 0.15),
            "gs_right": self.spec.get("gs_right", 0.92),  # 0.92,
            "gs_top": self.spec.get("gs_top", 0.92),
            "gs_bottom": self.spec.get("gs_bottom", 0.15),
        }


if __name__ == "__main__":

    print("Hello World!")
