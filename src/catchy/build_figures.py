"""
Build Figures Module
===================

This module extends the core scripting capabilities to handle the automated
rendering and conversion of SVG figures into rasterized formats (JPEG/PNG).

It utilizes markdown notes associated with each figure to extract metadata,
filters figures based on their completion status, and orchestrates the batch
conversion of SVGs using the Los Alamos custom tools. Rendered images are
subsequently distributed to their designated chapter directories within the
configured drive or file system.
"""
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


class ScriptBuildFigures(Script):
    """
    Executes the automated image building pipeline.

    Inheriting from the base :class:`Script`, this class discovers markdown notes
    related to figures, filters them by status (e.g., 'concluded', 'pending'),
    and drives the SVG-to-raster (JPEG/PNG) conversion process. It handles
    specific collection types (like 'cover', 'main text', 'box') and manages
    the final deployment of generated images to the correct output directories.

    :cvar TITLE: The display title of the script.
    :type TITLE: str
    :cvar LOG_NAME: Standard prefix for logging, specific to the build-images process.
    :type LOG_NAME: str
    :cvar DC_COLLECTIONS: Mapping of collection names to their file prefix representations.
    :type DC_COLLECTIONS: dict

    :ivar collection: The specific figure collection targeted for processing (defaults to "all").
    :vartype collection: str
    """
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
        """
        Executes the main figure rendering workflow for the current chapter.

        This method discovers relevant markdown notes based on the chosen collection,
        loads them into a metadata catalog, filters the notes by workflow status,
        and iterates over the filtered list to export the associated SVG files
        into raster images. Finally, it triggers the distribution of these files
        to the target drive.

        :returns: None
        """
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
        # heading_subsection(msg="Load data")
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

        df = df_full.copy()
        df_sub_1 = df.query("status == 'concluded'").copy()
        df_sub_2 = df[df["status"].str.contains("pending", na=False)]

        df = pd.concat([df_sub_1, df_sub_2]).reset_index(drop=True)

        self.print_info(f"{len(df)} notes filtered.")

        print("\n")
        print(df[["note_name", "title"]])
        print("\n")

        # --------------------------------------------------
        # Process
        # --------------------------------------------------
        # heading_subsection(msg="Render SVG")
        self.print_info(f"rendering SVGs ...")
        for _, row in tqdm(df.iterrows(), total=len(df), desc=" >>> ", unit="file"):

            f = Path(row["note_file"])
            fsvg = f.parent / f"{f.stem}.svg"

            if not fsvg.is_file():
                continue

            svg = FigureSVG()
            svg.load_data(fsvg)

            if self.write:

                current_opacity = 1
                is_not_box = True

                if row["collection"] == "box":
                    current_opacity = 0
                    is_not_box = False

                # pdf building
                self.build_pdf(f.stem, svg, row, opacity=current_opacity)

                # image building
                self.build_image(
                    f.stem, svg, row, build_jpeg=is_not_box, delete_png=is_not_box, opacity=current_opacity
                )



            else:
                time.sleep(0.01)

        self.send_to_drive()

        self.print_step("Done")
        return None

    def build_image(
        self, fname, svg_note, metadata, build_jpeg=False, delete_png=False, opacity=1
    ):
        """
        Renders a single SVG object into targeted raster formats.

        Parses layer metadata to determine the appropriate cropping boundaries
        and visibility of specific layers (e.g., hiding framing elements).

        :param fname: The base filename for the output image.
        :type fname: str
        :param svg_note: The loaded SVG figure object to be rendered.
        :type svg_note: FigureSVG
        :param metadata: The dictionary or pandas Series containing note-specific configurations.
        :type metadata: dict or pandas.Series
        :param build_jpeg: Flag to determine if a JPEG copy should be generated. Defaults to False.
        :type build_jpeg: bool
        :param delete_png: Flag to determine if the intermediate PNG should be removed. Defaults to False.
        :type delete_png: bool
        :param opacity: The opacity level to apply to the page background (0 to 1). Defaults to 1.
        :type opacity: int or float
        :returns: None
        """
        f = Path(metadata["note_file"])

        chapter_dir = f.parent

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
            svg_note.image_to_jpeg(file_input=fo, file_output=fo2)

        if delete_png:
            os.remove(fo)

        return None

    def build_pdf(self, fname, svg_note, metadata, opacity=1):
        """
        Renders a single SVG object into PDF.

        Parses layer metadata to determine the appropriate cropping boundaries
        and visibility of specific layers (e.g., hiding framing elements).

        :param fname: The base filename for the output image.
        :type fname: str
        :param svg_note: The loaded SVG figure object to be rendered.
        :type svg_note: FigureSVG
        :param metadata: The dictionary or pandas Series containing note-specific configurations.
        :type metadata: dict or pandas.Series
        :param opacity: The opacity level to apply to the page background (0 to 1). Defaults to 1.
        :type opacity: int or float
        :returns: None
        """
        f = Path(metadata["note_file"])

        chapter_dir = f.parent

        fo = STD_OUTPUT / f"{fname}_T1.pdf"

        ls_layers = svg_note.get_layers_labels()

        crop_id = metadata["size"]
        ls_hide = ["frames"]

        if "frame" in ls_layers:
            crop_id = "mainframe"
            ls_hide = ["frame"]

        svg_note.set_page_opacity(opacity=opacity)

        # export to pdf
        svg_note.to_pdf(
            file_output=fo,
            crop_id=crop_id,
            hide_layers=ls_hide,
        )

        return None

    def send_to_drive(self):
        """
        Distributes generated images to their final chapter directories.

        Scans the standard output directory for newly created T1
        files, and copies them to the respective ``FIGURES_DIR/chapterXX/T1``
        folders based on the prefixes of the filenames. Respects safe execution
        mode by simulating the copy process if ``self.write`` is False.

        :returns: None
        """
        folder = STD_OUTPUT
        ls_figs_jpeg = glob.glob(f"{folder}/C*_T1.jpeg")
        ls_figs_png = glob.glob(f"{folder}/C*_T1.png")
        ls_figs_pdf = glob.glob(f"{folder}/C*_T1.pdf")
        ls_figs = ls_figs_jpeg + ls_figs_png + ls_figs_pdf

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

    s = ScriptBuildFigures()
    s.run()
