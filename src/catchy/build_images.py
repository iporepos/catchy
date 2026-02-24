import time
import pprint, os
from pathlib import Path
# external
from tqdm import tqdm
import pandas as pd
# custom
from losalamos.notes import NoteCollFigure
from losalamos.figures import FigureSVG
from losalamos.tools.core import *
# local
from catchy.core import *


class ScriptBuildImages(Script):
    TITLE = "BUILD IMAGES FROM SVG FILES"
    LOG_NAME = LOG_PREFIX.format("build-images")

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

        # --------------------------------------------------
        # Load with progress bar
        # --------------------------------------------------
        #heading_subsection(msg="Load data")
        self.print_info("loading data ...")
        with tqdm(ls_notes, desc=" >>> ", unit="file") as pbar:
            nc.load_list(pbar)

        s = get_message(f"{len(ls_notes)} notes loaded to collection.")
        self.print_info(s)

        # --------------------------------------------------
        # Work dataframe
        # --------------------------------------------------
        #heading_subsection(msg="Filter data")
        self.print_info(f"filtering data ...")

        df_full = nc.catalog.copy()

        df = df_full.copy()
        df_sub_1 = df.query("status == 'concluded'").copy()
        df_sub_2 = df.query("status == 'pending'").copy()

        df = pd.concat([df_sub_1, df_sub_2]).reset_index(drop=True)

        self.print_info(f"{len(df)} notes filtered.")

        print("\n")
        print(df[["note_name", "title"]])
        print("\n")

        # --------------------------------------------------
        # Process
        # --------------------------------------------------
        #heading_subsection(msg="Render SVG")
        self.print_info(f"rendering SVGs ...")
        for _, row in tqdm(
                df.iterrows(),
                total=len(df),
                desc=" >>> ",
                unit="file"
        ):

            f = Path(row["note_file"])
            fsvg = f.parent / f"{f.stem}.svg"

            if not fsvg.is_file():
                continue

            svg = FigureSVG()
            svg.load_data(fsvg)

            if self.write:
                self.build_image(f.stem, svg, row, build_jpeg=True, delete_png=True, opacity=1)

                if row["collection"] == "box":
                    self.build_image(f.stem, svg, row, build_jpeg=False, delete_png=False, opacity=0)
            else:
                time.sleep(0.01)

        self.send_to_drive()

        self.print_step("Done")
        return None

    def build_image(self, fname, svg_note, metadata, build_jpeg=False, delete_png=False, opacity=1):
        f = Path(metadata["note_file"])

        chapter_dir = f.parent

        # output_dir = chapter_dir / "T1"
        # os.makedirs(output_dir, exist_ok=True)

        fo = STD_OUTPUT / f"{fname}_T1.png"
        fo2 = STD_OUTPUT / f"{fname}_T1.jpeg"

        ls_layers = svg_note.get_layers_labels()

        crop_id = metadata["size"]
        ls_hide = ["frames"]

        if "frame" in ls_layers:
            crop_id = "mainframe"
            ls_hide = ["frame"]

        svg_note.set_page_opacity(opacity=opacity)

        # export to png
        svg_note.to_image(
            file_output=fo,
            crop_id=crop_id,
            hide_layers=ls_hide,
        )
        if build_jpeg:
            svg_note.image_to_jpeg(
                file_input=fo,
                file_output=fo2
            )

        if delete_png:
            os.remove(fo)

        return None

    def send_to_drive(self):
        folder = STD_OUTPUT
        ls_figs_jpeg = glob.glob(f"{folder}/C*_T1.jpeg")
        ls_figs_png = glob.glob(f"{folder}/C*_T1.png")
        ls_figs = ls_figs_jpeg + ls_figs_png

        self.print_info("sending from outputs to drive")

        for f in tqdm(ls_figs, desc=" >>> ", unit="file"):
            p = Path(f)
            nm = p.stem
            chapter = "chapter" + nm.split("-")[0].replace("C", "")

            dst_folder = FIGURES_DIR / f"{chapter}/T1"
            f_dst = dst_folder / p.name
            if self.write:
                shutil.copy(src=f, dst=f_dst)
            else:
                time.sleep(0.01)

if __name__ == "__main__":

    s = ScriptBuildImages()
    s.run()
