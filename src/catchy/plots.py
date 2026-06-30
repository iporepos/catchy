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
from catchy.views import Plotter

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
        if self.spec["date_col"] == "year":
            self.date_col = "year"
            for i in range(len(self.data)):
                self.data[i] = self.handle_yearly_series(df=self.data[i])
        else:
            for i in range(len(self.data)):
                self.data[i][self.date_col] = pd.to_datetime(
                    self.data[i][self.date_col]
                )

    def handle_yearly_series(self, df):
        df[self.date_col] = df[self.date_col].astype(str)
        df[self.date_col] = df[self.date_col] + "-01-01"
        df[self.date_col] = pd.to_datetime(df[self.date_col])
        df.sort_values(by=self.date_col, inplace=True)
        return df

    def _draw(self):

        ax = self.axes[0]
        # first data

        dc = self.spec["data"]

        i = 0
        for ds in dc:
            df = self.data[i]

            lines = ds["lines"]
            for line in lines:
                x = line.get("x_field", "date")
                y = line.get("y_field", "Y")
                c = line.get("color", "black")
                linestyle = line.get("linestyle", "-")
                drawstyle = line.get("drawstyle", None)
                ax.plot(df[x], df[y], color=c, linestyle=linestyle, drawstyle=drawstyle)

            i = i + 1

        ylim = self.spec.get("ylim", None)
        if ylim:
            ax.set_ylim(ylim)

        xlim = self.spec.get("xlim", None)
        if xlim:
            ax.set_xlim(pd.to_datetime(xlim))


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
