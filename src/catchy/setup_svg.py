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
