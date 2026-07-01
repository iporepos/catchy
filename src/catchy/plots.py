"""
Plot Type Registry and Time-Series Implementation
=================================================

Provides a lightweight registry pattern for plot types and implements
:class:`PlotTimeSeries`, the primary concrete plotter in the catchy pipeline.

Architectural context
---------------------
Extends :mod:`catchy.views`. :class:`PlotTimeSeries` subclasses
:class:`~catchy.views.Plotter` and is auto-registered under the key
``"time-series"`` at import time via the :func:`register_plot` decorator.
Additional plot types can be added in this module or others using the same
decorator.

Key classes and functions
-------------------------
:data:`PLOT_REGISTRY`
    Module-level dict mapping registered plot-type names to their classes.
    Populated at import time. Do not write to this dict directly — use
    :func:`register_plot`.

:func:`register_plot`
    Class decorator that inserts a plot class into :data:`PLOT_REGISTRY`
    under a given name. Raises :exc:`ValueError` on duplicate names.

:func:`get_plot_class`
    Retrieves a class from :data:`PLOT_REGISTRY` by name. Raises
    :exc:`ValueError` if the name is not registered.

:class:`PlotTimeSeries`
    Renders date/year-based time-series from CSV data declared in a JSON
    spec. Supports daily date columns and annual (year-only) series via
    :meth:`handle_yearly_series`. Multiple datasets and multiple lines per
    dataset are drawn on a single axes object.

Usage
-----
Invoke via the ``__main__`` block, which reads a ``specs.json`` file from
the project data directory and renders all declared plots::

    python plots.py

Each entry in ``specs.json`` must declare a ``"class"`` key matching a
registered name (e.g. ``"time-series"``).

Dependencies
------------
    catchy.views    Plotter base class
    catchy.core     DATA_DIR (used in ``__main__`` only)
    pandas          Date parsing and DataFrame handling

Notes
-----
    - Importing this module is sufficient to register ``"time-series"`` in
      :data:`PLOT_REGISTRY`; no explicit registration call is needed.
    - Year-only series (``date_col == "year"``) are converted to
      ``YYYY-01-01`` timestamps so they can share axes with daily series.
"""

import pprint
import pandas as pd
from matplotlib.mlab import angle_spectrum

from catchy.views import Plotter
import matplotlib.patheffects as pe

# --------------------------------------------------
# SIMPLE REGISTRY
# --------------------------------------------------

PLOT_REGISTRY = {}


def register_plot(name):
    def decorator(cls):
        if name in PLOT_REGISTRY:
            raise ValueError(f"Plot name '{name}' already registered.")
        PLOT_REGISTRY[name] = cls
        return cls

    return decorator


def get_plot_class(name):
    try:
        return PLOT_REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown plot '{name}'.")


@register_plot("time-series")
class PlotTimeSeries(Plotter):

    def __init__(self, name, specs):
        super().__init__(name, specs)
        self.date_col = "date"

    def _load_data(self):
        super()._load_data()
        date_col = self.spec["date_col"]
        if date_col.lower() == "year":
            self.date_col = date_col
            for i in range(len(self.data)):
                self.data[i] = self.handle_yearly_series(df=self.data[i], date_col=date_col)
        elif date_col.lower() == "year_month":
            self.date_col = date_col
            for i in range(len(self.data)):
                self.data[i] = self.handle_monthly_series(df=self.data[i], date_col=date_col)
        else:
            for i in range(len(self.data)):
                self.data[i][self.date_col] = pd.to_datetime(
                    self.data[i][self.date_col]
                )

    @staticmethod
    def handle_monthly_series(df, date_col):
        df[date_col] = pd.to_datetime(
            df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-01"
        )
        df.sort_values(by=date_col, inplace=True)
        return df

    @staticmethod
    def handle_yearly_series(df, date_col):
        df[date_col] = df[date_col].astype(str) + "-01-01"
        df[date_col] = pd.to_datetime(df[date_col])
        df.sort_values(by=date_col, inplace=True)
        return df

    def _draw(self):
        ax = self.axes[0]
        dc = self.spec["data"]

        for i, ds in enumerate(dc):
            df = self.data[i]

            lines = ds.get("lines", [])
            for line in lines:
                x = line.get("x_field", "date")
                y = line.get("y_field", "Y")
                c = line.get("color", "black")
                linestyle = line.get("linestyle", "-")
                drawstyle = line.get("drawstyle", None)

                line_df = df
                line_xlim = line.get("xlim", None)
                if line_xlim:
                    lo, hi = pd.to_datetime(line_xlim[0]), pd.to_datetime(line_xlim[1])
                    line_df = df[(df[self.date_col] >= lo) & (df[self.date_col] <= hi)]

                y_values = line_df[y] / line.get("y_division", 1)
                ax.plot(line_df[x], y_values, color=c, linestyle=linestyle, drawstyle=drawstyle)

        ylim = self.spec.get("ylim", None)
        if ylim:
            ax.set_ylim(ylim)

        xlim = self.spec.get("xlim", None)
        if xlim:
            ax.set_xlim(pd.to_datetime(xlim))


@register_plot("time-series-mix")
class PlotTimeSeriesMix(Plotter):

    def __init__(self, name, specs):
        super().__init__(name, specs)
        self.date_cols = []

    def _load_data(self):
        super()._load_data()
        for i, ds in enumerate(self.spec["data"]):
            date_col = ds["date_col"]
            if date_col.lower() == "year":
                self.data[i] = PlotTimeSeries.handle_yearly_series(
                    df=self.data[i], date_col=date_col
                )
            elif date_col.lower() == "year_month":
                self.data[i] = PlotTimeSeries.handle_monthly_series(
                    df=self.data[i], date_col=date_col
                )
            else:
                self.data[i][date_col] = pd.to_datetime(self.data[i][date_col])
            self.date_cols.append(date_col)

    def _draw(self):
        ax = self.axes[0]
        dc = self.spec["data"]

        for i, ds in enumerate(dc):
            df = self.data[i]
            date_col = self.date_cols[i]

            # ---------------------------------------
            # ANOMALIES
            for fill in ds.get("anomalies", []):
                x = fill.get("x_field", "date")
                y = fill.get("y_field", "Y")
                c_pos = fill.get("color_pos", "steelblue")
                c_neg = fill.get("color_neg", "firebrick")
                alpha = fill.get("alpha", 0.8)
                zorder = fill.get("zorder", 0)

                line_df = df
                line_xlim = fill.get("xlim", None)
                if line_xlim:
                    lo, hi = pd.to_datetime(line_xlim[0]), pd.to_datetime(line_xlim[1])
                    line_df = df[(df[date_col] >= lo) & (df[date_col] <= hi)]

                vals = line_df[y] / fill.get("y_division", 1)
                ax.fill_between(
                    line_df[x], vals, 0,
                    where=(vals >= 0),
                    color=c_pos, alpha=alpha, zorder=zorder,
                    interpolate=True,
                    linewidth=0.3,
                )
                ax.fill_between(
                    line_df[x], vals, 0,
                    where=(vals < 0),
                    color=c_neg, alpha=alpha, zorder=zorder,
                    interpolate=True,
                    linewidth=0.3,
                )

            # ---------------------------------------
            # LINES
            for line in ds.get("lines", []):
                x = line.get("x_field", "date")
                y = line.get("y_field", "Y")
                c = line.get("color", "black")
                linestyle = line.get("linestyle", "-")
                drawstyle = line.get("drawstyle", None)

                line_df = df
                line_xlim = line.get("xlim", None)
                if line_xlim:
                    lo, hi = pd.to_datetime(line_xlim[0]), pd.to_datetime(line_xlim[1])
                    line_df = df[(df[date_col] >= lo) & (df[date_col] <= hi)]
                zorder = line.get("zorder", 0)
                y_values = line_df[y] / line.get("y_division", 1)
                ax.plot(line_df[x], y_values, color=c, linestyle=linestyle, drawstyle=drawstyle, zorder=zorder)

        ylim = self.spec.get("ylim", None)
        if ylim:
            ax.set_ylim(ylim)

        xlim = self.spec.get("xlim", None)
        if xlim:
            ax.set_xlim(pd.to_datetime(xlim))

@register_plot("bivar")
class PlotBivar(Plotter):

    def __init__(self, name, specs):
        super().__init__(name, specs)

    def _draw(self):
        ax = self.axes[0]
        dc = self.spec["data"]

        # set limits first so annotation offsets are computed against final ranges
        ylim = self.spec.get("ylim", None)
        if ylim:
            ax.set_ylim(ylim)

        xlim = self.spec.get("xlim", None)
        if xlim:
            ax.set_xlim(xlim)

        for i, ds in enumerate(dc):
            df = self.data[i]

            # ---------------------------------------
            # LINES
            for line in ds.get("lines", []):
                x_data = line.get("x_data", None)
                y_data = line.get("y_data", None)
                if x_data and y_data:
                    x_values = x_data
                    y_values = y_data
                else:
                    x = line.get("x_field", "X")
                    y = line.get("y_field", "Y")
                    x_values = df[x]
                    y_values = df[y]
                c = line.get("color", "black")
                linestyle = line.get("linestyle", "-")
                drawstyle = line.get("drawstyle", "default")
                zorder = line.get("zorder", 0)
                ax.plot(x_values, y_values, color=c, linestyle=linestyle,
                         drawstyle=drawstyle, zorder=zorder)

            # ---------------------------------------
            # POINTS
            for scatter in ds.get("points", []):
                x = scatter.get("x_field", "X")
                y = scatter.get("y_field", "Y")
                c = scatter.get("color", "black")
                marker = scatter.get("marker", "o")
                zorder = scatter.get("zorder", 0)
                alpha = scatter.get("alpha", 1)
                edgecolors = scatter.get("edgecolors", None)
                ax.scatter(df[x], df[y],
                           color=c, marker=marker,
                           zorder=zorder,
                           alpha=alpha,
                           edgecolors=edgecolors)

            # ---------------------------------------
            # ANNOTATIONS
            for text in ds.get("annotations", []):
                x = text.get("x_field", "X")
                y = text.get("y_field", "Y")
                tfield = text.get("text_field", "label")
                c = text.get("color", "black")
                zorder = text.get("zorder", 0)

                # offsets as % of axes range, converted to data units
                off_x_pct = text.get("offset_x_pct", 0)
                off_y_pct = text.get("offset_y_pct", 0)
                x0, x1 = ax.get_xlim()
                y0, y1 = ax.get_ylim()
                dx = (x1 - x0) * (off_x_pct / 100.0)
                dy = (y1 - y0) * (off_y_pct / 100.0)

                ha = text.get("ha", "left")
                va = text.get("va", "bottom")
                fontsize = text.get("fontsize", 5)

                halo_color = text.get("halo_color", None)
                halo_width = text.get("halo_width", 2)
                halo_alpha = text.get("halo_alpha", 0.7)

                path_effects = None
                if halo_color:
                    path_effects = [pe.withStroke(linewidth=halo_width, foreground=halo_color, alpha=halo_alpha)]

                for _, row in df.iterrows():
                    label = row[tfield]
                    if pd.isna(label):
                        continue
                    px, py = row[x], row[y]
                    ax.annotate(
                        str(label),
                        xy=(px, py),
                        xytext=(px + dx, py + dy),
                        textcoords="data",
                        color=c,
                        zorder=zorder,
                        ha=ha,
                        va=va,
                        fontsize=fontsize,
                        path_effects=path_effects,
                    )
        # ylim/xlim already applied above

        aspect = self.spec.get("aspect", None)
        if aspect:
            ax.set_aspect(aspect)


if __name__ == "__main__":
    from catchy.core import DATA_DIR
    from catchy.views import load_spec
    from pathlib import Path

    f = Path(__file__).parent.parent.parent / "data/specs.json"
    dc = load_spec(f)

    for name in dc:
        print(name)
        class_name = dc[name]["class"]
        cls = get_plot_class(class_name)
        plot = cls(name, dc[name])
        plot.write = True
        plot.show = False
        plot.run()
