#!/usr/bin/env python3
"""
Generate a square Gaussian random field ("blobby" texture) and save it
as a JPG image, with a filename timestamped to the second.

The field is built by taking white noise and smoothing it with a
Gaussian filter: the smoothing sigma controls how big the resulting
"blobs" look. A fixed RNG seed makes the output fully reproducible.

Usage:
    python gaussian_field.py
    python gaussian_field.py --size 512 --blob-size 25 --seed 7
    python gaussian_field.py --blob-size 5 --cmap gray --outdir ./out
    python gaussian_field.py --show           # also pop up a window with the image
    python gaussian_field.py --interactive    # prompts for each parameter
"""

import argparse
import os
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter


def generate_gaussian_field(size: int, blob_size: float, seed: int) -> np.ndarray:
    """
    Build a 2D Gaussian random field by smoothing white noise.

    size       : output field is (size x size) pixels
    blob_size  : std-dev (in pixels) of the smoothing kernel --
                 larger values -> bigger, smoother blobs;
                 smaller values -> finer, grainier texture
    seed       : deterministic RNG seed (same seed -> same image)
    """
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((size, size))

    # mode="wrap" keeps the field seamlessly tileable at the edges
    field = gaussian_filter(noise, sigma=blob_size, mode="wrap")

    # normalize to [0, 1] for display
    field -= field.min()
    field /= field.max()
    return field


def prompt_for_params(defaults: argparse.Namespace) -> argparse.Namespace:
    """
    Ask the user for each parameter on the command line, showing the
    current default/value in brackets. Pressing Enter keeps it.
    """
    def ask(prompt, current, cast):
        raw = input(f"{prompt} [{current}]: ").strip()
        if raw == "":
            return current
        try:
            return cast(raw)
        except ValueError:
            print(f"  Couldn't parse '{raw}', keeping {current}.")
            return current

    def ask_yes_no(prompt, current):
        raw = input(f"{prompt} [{'y' if current else 'n'}]: ").strip().lower()
        if raw == "":
            return current
        return raw in ("y", "yes", "true", "1")

    print("Enter values, or press Enter to keep the default shown in [brackets].")
    defaults.size = ask("Image size (pixels, square)", defaults.size, int)
    defaults.blob_size = ask("Blob size (smoothing sigma, pixels)", defaults.blob_size, float)
    defaults.seed = ask("Random seed", defaults.seed, int)
    defaults.cmap = ask("Colormap (e.g. viridis, gray, magma)", defaults.cmap, str)
    defaults.outdir = ask("Output directory", defaults.outdir, str)
    defaults.show = ask_yes_no("Show image in a window after saving?", defaults.show)
    return defaults


def main():
    parser = argparse.ArgumentParser(
        description="Generate a square Gaussian random field JPG."
    )
    parser.add_argument("--size", type=int, default=512,
                         help="image side length in pixels (default: 512)")
    parser.add_argument("--blob-size", type=float, default=20.0,
                         help="blob size / smoothing sigma in pixels (default: 20.0)")
    parser.add_argument("--seed", type=int, default=42,
                         help="deterministic random seed (default: 42)")
    parser.add_argument("--cmap", type=str, default="viridis",
                         help="matplotlib colormap, e.g. viridis, gray, magma (default: viridis)")
    parser.add_argument("--outdir", type=str, default=".",
                         help="output directory (default: current directory)")
    parser.add_argument("--show", action="store_true",
                         help="display the image in a window after saving")
    parser.add_argument("--interactive", action="store_true",
                         help="prompt for each parameter instead of using flags")
    args = parser.parse_args()

    if args.interactive:
        args = prompt_for_params(args)

    field = generate_gaussian_field(args.size, args.blob_size, args.seed)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gaussian_field_{timestamp}.jpg"
    os.makedirs(args.outdir, exist_ok=True)
    filepath = os.path.join(args.outdir, filename)

    # Build the figure so 1 pixel in the field = 1 pixel in the image
    dpi = 100
    fig = plt.figure(figsize=(args.size / dpi, args.size / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])  # axes fill the whole figure, no margins
    ax.imshow(field, cmap=args.cmap, origin="lower")
    ax.axis("off")
    fig.savefig(filepath, format="jpg", dpi=dpi)

    print(f"Saved: {filepath}")

    if args.show:
        plt.show()  # blocks until the window is closed
    plt.close(fig)


if __name__ == "__main__":
    main()
