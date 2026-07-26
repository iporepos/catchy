#!/usr/bin/env python3
"""
Generate an SVG plot of a synthetic monthly time series with a
non-sinusoidal (peaked) seasonal cycle, unbiased noise in the first
half of the record, and an exaggerated trend in the second half.

Usage:
    python gen_seasonal_svg.py --years 30 --seed 42 --wet-month 6
    python gen_seasonal_svg.py --years 20 --seed 7 --wet-month 12 --output out.svg
"""
import argparse
import numpy as np
import matplotlib.pyplot as plt


def seasonal_shape(months, wet_month, baseline=10.0, amplitude=15.0, sharpness=1.6):
    """Peaked (non-sinusoidal) seasonal cycle: a wrapped Gaussian-like bump
    centered on `wet_month`. `sharpness` controls how peaked (vs. broad)
    the bump is -- smaller sigma (i.e. larger sharpness) gives a sharper peak
    and flatter, non-sinusoidal troughs than a plain cosine would."""
    m = np.asarray(months) % 12
    diff = np.abs(m - wet_month)
    diff = np.minimum(diff, 12 - diff)  # circular distance in months
    sigma = 12 / (2 * sharpness) / np.pi * 2  # empirical scaling for a nice peak width
    return baseline + amplitude * np.exp(-0.5 * (diff / sigma) ** 2)


def build_series(years, seed, wet_month, trend_strength=1.5, noise_std=2.0):
    rng = np.random.default_rng(seed)
    n = years * 12
    months = np.arange(n)

    seasonal = seasonal_shape(months, wet_month)
    noise = rng.normal(0, noise_std, size=n)
    series = seasonal + noise

    half = n // 2
    first_half_avg = series[:half].mean()

    # Exaggerated linear trend added only to the second half: ramps from 0
    # up to (trend_strength - 1) times the first-half average by the final
    # step, so the last value ends up ~trend_strength x the first-half
    # average (default 1.5 = a 50% increase; e.g. 3.0 = a 200% increase).
    trend_fraction = trend_strength - 1.0
    target_increase = trend_fraction * first_half_avg
    trend = np.zeros(n)
    second_len = n - half
    trend[half:] = np.linspace(0, target_increase, second_len)
    series = series + trend

    return months, series, half, first_half_avg


def plot_series(months, series, half, first_half_avg, years, wet_month, output, show):
    dry_month = (wet_month + 6) % 12
    dates = months / 12.0  # in years, for a readable x-axis

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(dates[:half + 1], series[:half + 1], color="#2b6cb0",
            linewidth=1.2, label="Noise-only period")
    ax.plot(dates[half:], series[half:], color="#c53030",
            linewidth=1.2, label="Trend period")
    ax.axvline(dates[half], color="gray", linestyle="--", linewidth=0.8)

    ax.set_title(
        f"Synthetic seasonal time series ({years} years, monthly)\n"
        f"wet month={wet_month + 1}, dry month={dry_month + 1}, seed={_SEED}"
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("Value")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    if show:
        plt.show()
    else:
        fig.savefig(output, format="svg")
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, required=True, help="Number of years to simulate")
    parser.add_argument("--seed", type=int, required=True, help="Random seed for noise")
    parser.add_argument("--wet-month", type=int, required=True,
                         help="Wet season month, 1-12 (dry month is wet+6)")
    parser.add_argument("--output", type=str, default="seasonal_series.svg",
                         help="Output SVG file path (ignored if --show is used)")
    parser.add_argument("--trend-strength", type=float, default=1.5,
                         help="Multiplier applied to the first-half average to set the "
                              "final-step trend increase (default 1.5 = +50%%; e.g. 3 = +200%%)")
    parser.add_argument("--show", action="store_true",
                         help="Display the plot in an interactive window instead of saving it")
    args = parser.parse_args()

    global _SEED
    _SEED = args.seed
    wet_month_idx = (args.wet_month - 1) % 12  # convert to 0-based

    months, series, half, first_half_avg = build_series(
        args.years, args.seed, wet_month_idx, trend_strength=args.trend_strength
    )
    plot_series(months, series, half, first_half_avg, args.years, wet_month_idx,
                args.output, args.show)

    if not args.show:
        print(f"Saved: {args.output}")
    print(f"First-half average: {first_half_avg:.2f}")
    print(f"Trend added by final step: {(args.trend_strength - 1) * first_half_avg:.2f} "
          f"(= {(args.trend_strength - 1) * 100:.0f}% of first-half average)")


if __name__ == "__main__":
    main()