"""
Standardize SVG figure files across a chapter for consistent layer naming,
element IDs, and stroke widths.

Architectural context
---------------------
Sits in the figure-management pipeline between raw SVG authoring (Inkscape)
and the publication/export step. Subclasses :class:`catchy.core.Script`,
inheriting CLI parsing, write-gate confirmation, and chapter iteration.
Operates on the chapter set via ``--chapter`` at the command line and reads
figure metadata from Markdown note files under ``FIGURES_DIR``. All SVG
mutations are applied in-place via ``FigureSVG.save()``.

Usage
-----
Run directly::

    python setup_svg.py --chapter 3
    python setup_svg.py --chapter all -w

Write mode (``-w``) is required for mutations to be saved; omitting it
enters safe mode and no files are touched.

Behaviour
---------
For every ``.svg`` file paired with a chapter figure note (``C*-*-*.md``):

1. **Discover notes** — globs ``FIGURES_DIR/<chapter>/C*-*-*.md`` and loads
   them into a :class:`NoteCollFigure` collection.
2. **Layer rename** — renames the layer labelled ``"frame"`` to
   ``"frames"`` to match the canonical layer-naming convention.
3. **Element rename** — within the ``"frames"`` layer, renames
   ``"mainframe"`` to the size identifier from note metadata
   (e.g. ``"single"``, ``"double"``). Skipped silently when the note
   carries no ``size`` value.
4. **Stroke width** — sets ``stroke-width: 0.2`` on every element in the
   ``"frames"`` layer, overwriting any previously authored value.
5. **Save** — writes mutations back to the original ``.svg`` file.

Summarises counts of modified layers, elements, and stroke-width
assignments to stdout on completion.

Key paths
---------
* Input notes : ``FIGURES_DIR/<chapter>/C*-*-*.md``
* SVG files   : co-located with each note (same stem, ``.svg`` extension)

Dependencies
------------
* ``losalamos.notes.NoteCollFigure`` — figure note collection loader
* ``losalamos.figures.FigureSVG``    — SVG read/mutate/save wrapper
* ``losalamos.paths.FIGURES_DIR``    — project-level figures root
* ``catchy.core.Script``             — base class; provides ``--chapter``
                                      CLI, write gate, and ``run()``

Notes
-----
* SVG files are mutated **in-place** with no backup step. Run under
  version control or take manual backups before bulk processing.
* Notes with ``size is None`` silently skip the element-rename step —
  no warning is emitted.
* If zero notes are found for the chapter the method returns early with a
  warning and no files are touched.
"""

import shutil
import pprint
from pathlib import Path
from tqdm import tqdm
import pandas as pd
from losalamos.paths import FOLDER_TEMPLATES_DRAWINGS
from losalamos.notes import NoteCollFigure
from losalamos.figures import FigureSVG
from losalamos.tools.core import *
from catchy.core import *


class ScriptStandardize(Script):
    TITLE = "STANDARDIZE SVG FILES"
    LOG_NAME = LOG_PREFIX.format("standardize-svg")

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
        with tqdm(ls_notes, desc=" >>> ", unit="file") as pbar:
            nc.load_list(pbar)

        s = get_message(f"{len(ls_notes)} notes loaded to collection.")
        self.print_info(s)

        # --------------------------------------------------
        # Work dataframe
        # --------------------------------------------------
        # heading_subsection(msg="Filter data")
        self.print_info(f"filtering data ...")
        df = nc.catalog.copy()
        print("\n")
        print(df[["note_name", "title", "status"]])
        print("\n")

        # --------------------------------------------------
        # Process
        # --------------------------------------------------
        counter_layers = 0
        counter_elements = 0
        counter_strokes = 0

        self.print_info(f"processing data")
        for _, row in tqdm(df.iterrows(), total=len(df), desc=" >>> ", unit="files"):
            # for row in df.to_dict(orient='records'):

            # =============================
            # Load figure
            f = Path(row["note_file"])
            fsvg = f.parent / f"{f.stem}.svg"
            fig = FigureSVG()
            fig.load_data(file_data=fsvg)

            # =============================
            # Rename 'frame' layer
            dc_layers = fig.get_layers()
            ls_layers = list(dc_layers.keys())
            if "frame" in ls_layers:
                # pprint.pp(ls_layers)
                fig.rename_layer(label="frame", new_label="frames")
                counter_layers += 1

            # =====================================
            # Get elements
            dc_elements = fig.get_layer_elements(label="frames")
            ls_elements = list(dc_elements.keys())

            # =====================================
            # Rename 'mainframe' elements to 'size'
            #   check for size definition
            size = row["size"]
            if size is not None:
                if "mainframe" in ls_elements:
                    fig.rename_element_id(old_id="mainframe", new_id=size)
                    counter_elements += 1

            # =============================
            # Set stroke-width
            for k in ls_elements:
                fig.set_property(
                    element=dc_elements[k]["element"], key="stroke-width", value="0.2"
                )
                counter_strokes += 1

            fig.save()

        self.print_info(f"{counter_layers} notes standardized for layers.")
        self.print_info(f"{counter_elements} notes standardized for elements.")
        self.print_info(f"{counter_strokes} notes standardized for stroke-width.")
        self.print_step("Done")
        return None


if __name__ == "__main__":

    s = ScriptStandardize()
    s.run()

    print("Hello")
