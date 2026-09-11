#!/usr/bin/env python3
"""
Generate an SVG plot with rainfall and runoff (streamflow) time series,
each in its own subplot, read from CSV files and configured via a JSON
config file.

Usage:
    python plot_rain_runoff.py --config config.json
    python plot_rain_runoff.py --config config.json --output out.svg

Config JSON schema:
{
    "rain": {
        "csv": {
            "path": "path/to/rain.csv",
            "separator": ",",
            "variable_field": "precip_mm",
            "date_field": "date"
        }
    },
    "flow": {
        "csv": {
            "path": "path/to/flow.csv",
            "separator": ",",
            "variable_field": "flow_m3s",
            "date_field": "date"
        }
    },
    "plot": {
        "date_start": "2000-01-01",
        "date_end": "2020-12-31"
    }
}
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def get_required(d, key, context):
    """Fetch a required key from a dict, raising a clear error if missing."""
    if key not in d:
        raise KeyError(f"missing required key '{key}' in {context}")
    return d[key]


def load_series(csv_cfg, label):
    """Load a single date-indexed series from a CSV file per its config block."""
    path = get_required(csv_cfg, "path", f"{label}.csv")
    sep = csv_cfg.get("separator", ",")
    var_field = get_required(csv_cfg, "variable_field", f"{label}.csv")
    date_field = get_required(csv_cfg, "date_field", f"{label}.csv")

    if not Path(path).is_file():
        raise FileNotFoundError(f"[{label}] CSV file not found: {path}")

    df = pd.read_csv(path, sep=sep)

    for field in (date_field, var_field):
        if field not in df.columns:
            raise KeyError(
                f"[{label}] field '{field}' not found in {path}. "
                f"Available columns: {list(df.columns)}"
            )

    df[date_field] = pd.to_datetime(df[date_field], errors="coerce")
    if df[date_field].isna().all():
        raise ValueError(f"[{label}] could not parse any dates in field '{date_field}'")

    df = df[[date_field, var_field]].dropna(subset=[date_field])
    df = df.set_index(date_field).sort_index()

    series = pd.to_numeric(df[var_field], errors="coerce").dropna()
    series.name = label
    return series


def clip_window(series, date_start, date_end, label):
    """Restrict a series to [date_start, date_end]; raise a clear error if empty."""
    windowed = series.loc[date_start:date_end]
    if windowed.empty:
        span = (
            f"{series.index.min()} to {series.index.max()}"
            if not series.empty else "no data at all"
        )
        raise ValueError(
            f"[{label}] the selected window ({date_start} to {date_end}) "
            f"contains no data. Series spans: {span}."
        )
    return windowed


def plot_rain_runoff(rain, flow, date_start, date_end, output, show=False):
    fig, (ax_rain, ax_flow) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)

    # Rainfall subplot
    ax_rain.bar(rain.index, rain.values, width=1.0, color="#2b6cb0", label="Rainfall")
    ax_rain.set_ylabel("Rainfall (mm)")
    ax_rain.set_ylim(0, rain.max() * 1.05)
    ax_rain.grid(alpha=0.3)
    ax_rain.legend(loc="upper right")
    ax_rain.set_title(f"Rainfall and Runoff ({date_start} to {date_end})")

    # Runoff / flow subplot
    ax_flow.plot(flow.index, flow.values, color="#c53030", linewidth=1.2, label="Runoff")
    ax_flow.set_ylabel("Flow (m³/s)")
    ax_flow.set_ylim(0, flow.max() * 1.05)
    ax_flow.set_xlabel("Date")
    ax_flow.grid(alpha=0.3)
    ax_flow.legend(loc="upper right")

    ax_flow.set_xlim(pd.Timestamp(date_start), pd.Timestamp(date_end))

    fig.tight_layout()

    if show:
        plt.show()
    else:
        fig.savefig(output, format="svg")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=str, required=True, help="Path to JSON config file")
    parser.add_argument("--output", type=str, default=None,
                         help="Output SVG file path. Defaults to 'rain_runoff.svg' "
                              "in the same folder as --config.")
    parser.add_argument("--show", action="store_true",
                         help="Display the plot in an interactive window instead of "
                              "saving it, so axes/limits/style can be fine-tuned first.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        sys.exit(f"Error: config file not found: {config_path}")

    if args.output is None:
        output_path = config_path.parent / "rain_runoff.svg"
    else:
        output_path = Path(args.output)

    try:
        with open(config_path) as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"Error: could not parse config JSON: {e}")

    try:
        rain_cfg = get_required(cfg, "rain", "config")
        flow_cfg = get_required(cfg, "flow", "config")
        plot_cfg = get_required(cfg, "plot", "config")

        rain_full = load_series(get_required(rain_cfg, "csv", "rain"), "rain")
        flow_full = load_series(get_required(flow_cfg, "csv", "flow"), "flow")

        date_start = get_required(plot_cfg, "date_start", "plot")
        date_end = get_required(plot_cfg, "date_end", "plot")

        rain = clip_window(rain_full, date_start, date_end, "rain")
        flow = clip_window(flow_full, date_start, date_end, "flow")
    except (FileNotFoundError, KeyError, ValueError) as e:
        sys.exit(f"Error: {e}")

    plot_rain_runoff(rain, flow, date_start, date_end, output_path, show=args.show)

    if not args.show:
        print(f"Saved: {output_path}")
    print(f"Rain window: {rain.index.min()} -> {rain.index.max()}, max={rain.max():.2f}")
    print(f"Flow window: {flow.index.min()} -> {flow.index.max()}, max={flow.max():.2f}")


if __name__ == "__main__":
    main()