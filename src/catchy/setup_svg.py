"""
ScriptSetupSVG — Batch SVG Template Initializer
================================================
Copies a blank SVG template (_wien.svg) alongside each figure note that is
currently in 'stand-by' status, seeding it for illustration work.

Subclasses :class:`losalamos.tools.core.Script`, which provides CLI argument
parsing (``--chapter``, ``--write``), safe/write mode gating with user
confirmation, standard console logging (INFO / STEP / WARN), and chapter
iteration over the range defined in ``config.local.json``.

Usage
-----
    python setup_svg.py --chapter <N> [--collection COLLECTION] [-w]

Arguments
---------
    --chapter       Chapter number to process, or ``all`` to iterate over
                    [CHAPTER_START, CHAPTER_END] as set in config.local.json.
                    Inherited from Script.get_parser().
    --collection    Figure collection to target (default: all):
                        cover      → prefix "cov", for cover illustrations
                        main text  → prefix "mtx", for body figures
                        biography  → prefix "bio", for biography boxes
                        box        → prefix "box", for sidebar boxes
                        all        → wildcard "*", all collections
    -w / --write    Enable write mode. Without this flag the script runs in
                    safe mode (no files written). With it, a confirmation
                    prompt is shown before any data is touched.

Behaviour
---------
    1. Resolves src_dir via Script.set_src_dir() →
       FIGURES_DIR / chapter<NN>.
    2. Globs FIGURES_DIR / chapter<NN> / C*-<col>-*.md for note files.
    3. Loads matched paths into a NoteCollFigure collection.
    4. Filters the catalog DataFrame to rows where status == 'stand-by'.
    5. For each filtered note, copies _wien.svg to <note_stem>.svg in the
       same directory (shutil.copy — overwrites silently on repeat runs).

Key paths (resolved from config.local.json at import time)
-----------------------------------------------------------
    Template SVG:   FOLDER_TEMPLATES_DRAWINGS / "_wien.svg"
    Notes root:     FIGURES_DIR  (BASE_DIR / "figures/main")
    Output:         FIGURES_DIR / chapter<NN> / <note_stem>.svg

Dependencies
------------
    losalamos.paths       FOLDER_TEMPLATES_DRAWINGS
    losalamos.notes       NoteCollFigure
    losalamos.tools.core  Script, LOG_PREFIX, FIGURES_DIR
    catchy.core           (project-level utilities)

Notes
-----
    - Only 'stand-by' notes receive an SVG; notes at any other status are
      skipped automatically by the DataFrame filter.
    - Re-running is safe: shutil.copy overwrites without error.
    - If 0 notes match, a WARN is printed and the script exits cleanly.
    - Write-mode gate is inherited from Script.handle_mode() but has no
      meaningful effect here since shutil.copy is always executed; consider
      guarding the copy call with ``if self.write`` in a future revision.
"""
import shutil
from pathlib import Path
from tqdm import tqdm
import pandas as pd
from losalamos.paths import FOLDER_TEMPLATES_DRAWINGS
from losalamos.notes import NoteCollFigure
from losalamos.tools.core import *

from catchy.core import *


class ScriptSetupSVG(Script):
    TITLE = "SETUP SVG FILES"
    LOG_NAME = LOG_PREFIX.format("setup-svg")

    DC_COLLECTIONS = {
        "cover": "cov",
        "main text": "mtx",
        "biography": "bio",
        "box": "box",
        "all": "*",
    }

    def __init__(self):
        super().__init__()
        self.collection = None

    def get_parser(self):
        parser = super().get_parser()

        parser.add_argument("--collection", default="all", help="Collection")

        return parser

    def set_arguments(self, args):
        super().set_arguments(args)
        self.collection = args.collection

    def processing(self):

        src_file = FOLDER_TEMPLATES_DRAWINGS / "_wien.svg"

        c_n = self.current_chapter
        self.set_src_dir(c_n=self.current_chapter)
        nc = NoteCollFigure()

        # --------------------------------------------------
        # Discover notes
        # --------------------------------------------------

        col = self.DC_COLLECTIONS[self.collection]

        chn = self.get_chapter_folder_name(c_n)
        ls_notes = list(FIGURES_DIR.glob(f"./{chn}/C*-{col}-*.md"))

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

        df_full = nc.catalog.copy()
        df = df_full.query("status == 'stand-by'").reset_index(drop=True)

        self.print_info(f"{len(df)} notes filtered.")

        print("\n")
        print(df[["note_name", "title"]])
        print("\n")

        # --------------------------------------------------
        # Process
        # --------------------------------------------------
        c = 0
        for _, row in tqdm(df.iterrows(), total=len(df), desc=" >>> ", unit="files"):
            f = Path(row["note_file"])
            fsvg = f.parent / f"{f.stem}.svg"
            # print(fsvg)
            shutil.copy(src=src_file, dst=fsvg)
            c += 1

        self.print_info(f"{c} notes copied.")
        self.print_step("Done")
        return None


if __name__ == "__main__":

    s = ScriptSetupSVG()
    s.run()
