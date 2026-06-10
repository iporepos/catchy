"""
Head docs
"""
import re
import shutil
import pprint
from html.parser import commentclose
from pathlib import Path
from tqdm import tqdm
import pandas as pd
from losalamos.notes import NoteCollFigure, NoteFigure
from losalamos.tools.core import *
from catchy.core import *

FLAG = ">>> Ipo@2026-06 SVG Reformatted. T2 fine-tune adjust margins and symbols"

class ScriptReformatFlags(Script):
    TITLE = "REFORMAT FLAGS"
    LOG_NAME = LOG_PREFIX.format("reformat-svg-flags")

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

        pprint.pp(nc.collection)

        print(df.info())
        print("\n")
        print(df[["note_name", "title", "status"]])
        print("\n")

        # --------------------------------------------------
        # Process
        # --------------------------------------------------
        counter = 0

        self.print_info(f"processing data")
        #for _, row in tqdm(df.iterrows(), total=len(df), desc=" >>> ", unit="files"):
        for row in df.to_dict(orient='records'):
            # =============================
            # find note
            n = row["note_name"]
            dc_metadata = nc.collection[n].metadata
            comment = dc_metadata.get("comment", None)


            if comment is None:
                comment = ''

            comment = comment.replace('"', '')

            if FLAG in comment:
                continue

            comment = comment + ' ' + FLAG
            nc.collection[n].metadata['comment'] = f'"{comment}"'
            nc.collection[n].save()
            counter += 1

        self.print_info(f"{counter} notes flagged.")
        self.print_step("Done")
        return None


if __name__ == "__main__":

    s = ScriptReformatFlags()
    s.run()