import pprint
import time

# external
from tqdm import tqdm
import pandas as pd

from losalamos.notes import NoteCollFigure
from losalamos.paths import FOLDER_TEMPLATES_DOCUMENTS
from losalamos.tools.core import *
# local
from catchy.core import *

class ScriptBuildCatalog(Script):
    TITLE = "BUILD CATALOG"
    LOG_NAME = LOG_PREFIX.format("build-catalog")

    DC_COLLECTIONS = {
        "cover": "cov",
        "main text": "mtx",
        "biography": "bio",
        "box": "box",
        "all": "*",
    }


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

        # --------------------------------------------------
        # Load with progress bar
        # --------------------------------------------------
        # heading_subsection(msg="Load data")
        self.print_info("loading data ...")
        with tqdm(ls_notes, desc=" >>> ", unit="file") as pbar:
            nc.load_list(pbar)

        s = get_message(f"{len(ls_notes)} notes loaded to collection.")
        self.print_info(s)

        df_full = nc.catalog.copy()
        df = df_full.copy()

        print("\n")
        print(df[["note_name", "title"]])
        print("\n")

        # --------------------------------------------------
        # Process
        # --------------------------------------------------
        self.print_info(f"generating catalog ...")

        # load template
        self.print_info(f"loading template ...")
        f_template = FOLDER_TEMPLATES_DOCUMENTS / "_catalog_figure.tex"

        with f_template.open("r", encoding="utf-8") as f:
            content = f.read()

        self.print_info(f"handling individual figures ...")
        for _, row in tqdm(
                df.iterrows(),
                total=4, #len(df),
                desc=" >>> ",
                unit="file"
        ):
            content_print = content[:]
            #print("\n")
            #pprint.pp(row)
            nm = row.get("name", "unknown").replace('"', '')
            dc = {}
            dc["[[status]]"] = self.get_status(row)
            dc["[[title]]"] = row.get("title", "untitled").replace('"', '')
            dc["[[label]]"] = nm
            dc["[[file_mvp]]"] = self.get_file_path(row, tier="T1")
            dc["[[file_draft]]"] = self.get_file_path(row, tier="T0")
            dc["[[file]]"] = self.get_file(row)
            dc["[[collection]]"] = row.get("collection", "unknown").replace('"', '')
            dc["[[category]]"] = self.get_category(row)
            dc["[[chapter]]"] = "chapter" + nm.split("-")[0].replace("C", "")
            dc["[[comment]]"] = self.get_comment(row)
            dc["[[credits]]"] = self.get_credits(row)
            dc["[[width]]"] = self.get_width(row)
            dc["[[status_mvp]]"] = self.get_status(row)
            dc["[[status_ftp]]"] = self.get_status(row)

            #pprint.pp(dc)

            for k in dc:
                content_print = content_print.replace(k, dc[k])


            if self.write:
                nm = row['name'].replace('"', '')
                fo = STD_OUTPUT / f"{nm}.tex"
                print(fo)
                fo.write_text(content_print, encoding="utf-8")
            else:
                time.sleep(0.02)

    def get_status(self, dc):
        s = dc.get("status", "stand-by")
        sts = ""

        if s == "concluded":
            sts = r"\colorbox{LimeGreen}{concluded}"
        elif "pending" in s:
            sts = r"\colorbox{YellowOrange}{" + s + "}"
        elif s == "stand-by":
            sts = r"\colorbox{RedOrange}{stand-by}"
        else:
            sts = r"\colorbox{Gray}{unknown}"

        return sts

    def get_file_path(self, dc, tier="T1"):
        sts = dc.get("status", "stand-by")
        fp = "example-image"
        s = dc.get("name").replace('"', '')
        nm = s.split("-")[0].replace("C", "")
        f = self.get_file(dc)
        if tier == "T1":
            if sts != "stand-by":
                fp = f"figs/chapter{nm}/{tier}/{f}"
        else:
            fp = f"figs/chapter{nm}/{tier}/{f}".replace("png", "jpeg")
        return fp

    def get_file(self, dc):
        s = dc.get("name").replace('"', '')
        nm = s.split("-")[0].replace("C", "")
        collection = dc.get("collection")
        suff = "jpeg"
        if collection == "box":
            suff = "png"
        f = f"{s}.{suff}"
        return f

    def get_comment(self, dc):

        return "TODO"

    def get_credits(self, dc):

        return "TODO"

    def get_width(self, dc):

        return "TODO"

    def get_category(self, dc):
        s = dc.get("category", "unknown")
        if s is None:
            return "unknown"
        else:
            return s.replace('"', '')
if __name__ == "__main__":

    s = ScriptBuildCatalog()
    s.run()
