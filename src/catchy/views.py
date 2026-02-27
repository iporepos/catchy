from catchy.core import DATA_DIR, FIGURES_DIR
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from plans import viewer

DC_COLORS = {"rain": "steelblue", "streamflow": "navy"}  # "#6d7fa2ff",  # "#223b85ff"


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
        specs = self.get_view_specs()
        # setup fig
        self.fig, self.gs = viewer.build_fig(specs=specs)
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
        # ship fig
        # ----------------------------------------------------
        viewer.ship_fig(
            self.fig,
            show=self.show,
            file_output=str(self.output_file),
            dpi=self.dpi,
        )

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

        size = self.spec["size"]
        w = viewer.FIG_SIZES[size]["w"]

        h = self.spec.get("height", None)
        if h is None:
            h = viewer.FIG_SIZES[size]["h"]

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
