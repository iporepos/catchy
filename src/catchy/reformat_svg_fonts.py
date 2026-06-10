"""
Reformat SVG Fonts
==================

Applies a uniform font family to all SVG figure files in a chapter.

Architectural context
---------------------
Sits in the figure-management pipeline as a cleanup/normalisation step,
typically run after SVG authoring to enforce typographic consistency before
publication. Subclasses :class:`catchy.core.Script`, inheriting CLI parsing,
write-gate confirmation, and chapter iteration. Reads figure metadata from
Markdown note files under ``FIGURES_DIR`` and applies font mutations in-place
via ``FigureSVG.save()``.

Usage
-----
Run directly::

    python reformat_fonts.py --chapter 3
    python reformat_fonts.py --chapter all -w

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
3. **Font reset** — calls ``FigureSVG.set_font_layers()`` with
   ``font_family="Helvetica LT Std"`` across all layers of the SVG.
4. **Save** — writes mutations back to the original ``.svg`` file.

Summarises the count of reformatted files to stdout on completion.

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
* Notes with ``status == 'stand-by'`` are silently skipped; all other
  status values are included.
* If zero notes are found for the chapter the method returns early with a
  warning and no files are touched.
* Font availability is not validated — if ``"Helvetica LT Std"`` is not
  installed on the target machine, SVGs will render with a fallback font
  at export time without raising an error here.
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


class ScriptReformatFonts(Script):
    TITLE = "REFORMAT SVG FONTS"
    LOG_NAME = LOG_PREFIX.format("reformat-svg-fonts")

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
        self.print_info(f"filtering data ...")
        df = nc.catalog.copy()
        df = df.query("status != 'stand-by'").reset_index(drop=True)

        print("\n")
        print(df[["note_name", "title", "status"]])
        print("\n")

        # --------------------------------------------------
        # Process
        # --------------------------------------------------
        counter_fonts = 0

        self.print_info(f"processing data")
        # for row in df.to_dict(orient='records'):
        for _, row in tqdm(df.iterrows(), total=len(df), desc=" >>> ", unit="files"):

            # =============================
            # Load figure
            f = Path(row["note_file"])
            fsvg = f.parent / f"{f.stem}.svg"
            fig = FigureSVG()
            fig.load_data(file_data=fsvg)

            # =======================================
            # Reset fonts across all available layers
            fig.set_font_layers(font_family="Helvetica LT Std")
            counter_fonts += 1

            fig.save()

        self.print_info(f"{counter_fonts} notes reformatted for fonts.")
        self.print_step("Done")
        return None


if __name__ == "__main__":

    s = ScriptReformatFonts()
    s.run()
