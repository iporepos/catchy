"""
Reformat SVG Sizes
==================

Corrects layer matrix transforms and sets canonical pixel widths on frame
elements for all active SVG figure files in a chapter.

Architectural context
---------------------
Sits in the SVG reformat pipeline after :mod:`reformat_svg_fonts` and before
:mod:`reformat_svg_flags`. Subclasses :class:`catchy.core.Script`, inheriting
CLI parsing, write-gate confirmation, and chapter iteration. Reads figure
metadata from Markdown note files under ``FIGURES_DIR`` and applies SVG
mutations in-place via ``FigureSVG.save()``.

Usage
-----
Run directly::

    python reformat_svg_sizes.py --chapter 3
    python reformat_svg_sizes.py --chapter all -w

Write mode (``-w``) is required for mutations to be saved; omitting it
enters safe mode and no files are touched.

Behaviour
---------
For every active ``.svg`` file paired with a chapter figure note
(``C*-*-*.md``):

1. **Discover notes** — globs ``FIGURES_DIR/<chapter>/C*-*-*.md`` and loads
   them into a :class:`NoteCollFigure` collection.
2. **Filter** — excludes notes with ``status == 'stand-by'``; only active
   figures are processed.
3. **Fix layer scale** — calls :func:`fix_layer_scale` on the ``"frames"``
   layer, resetting matrix scale components to 1 while preserving any
   translation offsets. No-ops if the layer is absent or the scale is already
   correct.
4. **Set frame widths** — for each size code present as an element ID in
   ``"frames"`` (``L``, ``M``, ``S``), sets the ``width`` property to the
   canonical pixel value defined in :data:`DC_NEW_WIDTHS`.
5. **Save** — writes mutations back to the original ``.svg`` file.

Module-level constants
----------------------
:data:`DC_NEW_WIDTHS`
    Maps size codes to canonical pixel widths: ``L=172``, ``M=126``,
    ``S=83.5``.

:func:`fix_layer_scale`
    Standalone helper that parses a ``matrix(a,b,c,d,e,f)`` transform on the
    named layer and resets the scale components (``a``, ``d``) to 1, preserving
    translation (``e``, ``f``) and shear (``b``, ``c``). Handles only
    ``matrix()`` form; ``scale()`` and ``translate()`` forms are left untouched.
    Safe to call on files without a transform attribute.

Key paths
---------
* Input notes : ``FIGURES_DIR/<chapter>/C*-*-*.md``
* SVG files   : co-located with each note (same stem, ``.svg`` extension)

Dependencies
------------
* ``losalamos.notes.NoteCollFigure`` — figure note collection loader
* ``losalamos.figures.FigureSVG``    — SVG read/mutate/save wrapper
* ``catchy.core.Script``             — base class; provides ``--chapter``
                                      CLI, write gate, and ``run()``

Notes
-----
* SVG files are mutated **in-place** with no backup step. Run under
  version control or take manual backups before bulk processing.
* The class in this module is named ``ScriptReformatFonts`` — a copy-paste
  artifact; the correct name should be ``ScriptReformatSizes``.
* Notes with ``status == 'stand-by'`` are silently skipped.
* If zero notes are found for the chapter, the method returns early with
  a warning and no files are touched.
"""

import re
import shutil
import pprint
from pathlib import Path

from pyogrio import list_layers
from tqdm import tqdm
import pandas as pd
from losalamos.paths import FOLDER_TEMPLATES_DRAWINGS
from losalamos.notes import NoteCollFigure
from losalamos.figures import FigureSVG
from losalamos.tools.core import *
from catchy.core import *

DC_NEW_WIDTHS = {"L": str(172), "M": str(126), "S": str(83.5)}


def fix_layer_scale(fig, label="frames"):
    """
    Reset the scale factors of a layer's matrix transform to 1,
    preserving any translation offsets.

    In Inkscape, resizing a layer via the GUI stores the operation as a
    matrix transform on the layer group rather than updating child element
    coordinates. This causes a mismatch between the XML attribute values
    and the rendered dimensions. This function corrects that by setting
    the scale components of the matrix to 1 while keeping the translation
    intact, so that rect widths in the XML match what is rendered.

    Only matrix() transforms are handled. Layers with no transform, or
    with scale()/translate() forms, are left untouched. Safe to call on
    files that do not have the transform.

    :param fig: A loaded FigureSVG instance.
    :type fig: FigureSVG
    :param label: Inkscape layer label to fix. Default value = ``frames``
    :type label: str
    :return: None
    :rtype: NoneType
    """
    # abort if the target layer does not exist in this file
    layers = fig.get_layers()
    if label not in layers:
        return

    # abort if the layer has no transform attribute
    layer = layers[label]
    transform = layer.get("transform", "")
    if not transform:
        return

    # only handle matrix(a,b,c,d,e,f) — ignore scale() or translate() forms
    m = re.fullmatch(
        r"matrix\(\s*([^,]+),([^,]+),([^,]+),([^,]+),([^,]+),([^,]+)\s*\)",
        transform.strip(),
    )
    if m is None:
        return

    # unpack the six matrix components:
    # a, d = X and Y scale; b, c = shear; e, f = X and Y translation
    a, b, c, d, e, f = [float(m.group(i)) for i in range(1, 7)]

    # abort if scale is already 1 on both axes — nothing to fix
    if abs(a - 1.0) < 1e-9 and abs(d - 1.0) < 1e-9:
        return

    # reset scale to 1 on both axes, preserve translation and shear
    layer.set("transform", f"matrix(1,{b},{c},1,{e},{f})")


class ScriptReformatFonts(Script):
    TITLE = "REFORMAT SVG SIZES"
    LOG_NAME = LOG_PREFIX.format("reformat-svg-sizes")

    def __init__(self):
        super().__init__()

    def processing(self):

        c_n = self.current_chapter
        self.set_src_dir(c_n=self.current_chapter)
        nc = NoteCollFigure()

        # --------------------------------------------------
        # Discover notes
        # --------------------------------------------------

        chn = self.get_chapter_folder_name(c_n)
        ls_notes = list(FIGURES_DIR.glob(f"./{chn}/C*-*-*.md"))

        if len(ls_notes) == 0:
            self.print_warn("WARNING >>> 0 notes found")
            return None

        self.print_info("loading data ...")
        with tqdm(ls_notes, desc=" >>> ", unit="file", bar_format=PBAR_FORMAT) as pbar:
            nc.load_list(pbar)

        s = get_message(f"{len(ls_notes)} notes loaded to collection.")
        self.print_info(s)

        # --------------------------------------------------
        # Work dataframe
        # --------------------------------------------------
        self.print_info(f"filtering data ...")
        df = nc.catalog.copy()
        df = df.query("status != 'stand-by'").reset_index(drop=True)

        print("\n")
        print(df[["note_name", "title", "status"]])
        print("\n")

        # --------------------------------------------------
        # Process
        # --------------------------------------------------
        counter = 0

        self.print_info(f"processing data")
        for _, row in tqdm(df.iterrows(), total=len(df), desc=" >>> ", unit="files", bar_format=PBAR_FORMAT):
            # for row in df.to_dict(orient='records'):
            # =============================
            # Load figure
            f = Path(row["note_file"])

            fsvg = f.parent / f"{f.stem}.svg"
            fig = FigureSVG()
            fig.load_data(file_data=fsvg)

            # =======================================
            # Fix layer scale before setting widths
            fix_layer_scale(fig, label="frames")

            # =======================================
            # Set width property
            dc_layers = fig.get_layers()
            dc_elements = fig.get_layer_elements(label="frames")
            # pprint.pp(dc_elements)

            for k in list(DC_NEW_WIDTHS.keys()):
                if k in dc_elements:
                    fig.set_property(
                        element=dc_elements[k]["element"],
                        key="width",
                        value=DC_NEW_WIDTHS[k],
                    )

            fig.save()
            counter += 1

        self.print_info(f"{counter} notes reformatted for sizes.")
        self.print_step("Done")
        return None


if __name__ == "__main__":

    s = ScriptReformatFonts()
    s.run()
