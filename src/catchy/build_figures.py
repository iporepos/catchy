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

Passing ``--recent [HOURS]`` narrows a chapter build to the figures that are
not in 'stand-by' status and whose SVG was modified within the last ``HOURS``
hours (24 by default). Only the figures built in the current run are sent to
their chapter directories.

In write mode (``-w``), the overwrite confirmation is deferred until the batch
size is known: batches smaller than ``LARGE_BATCH`` (3) figures are written
without asking, larger ones ask once per run. With ``--chapter all`` the
batch size is counted per chapter.
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

    A single figure may also be targeted directly via ``--figure``, passing
    its label (e.g. ``"C01-mtx-hydro"``). Since the chapter is always encoded
    as the leading ``C<nn>`` token of the label, :meth:`set_arguments`
    injects it into ``args.chapter`` automatically, so ``--chapter`` is not
    required in that mode (an explicit ``--chapter`` is still respected if
    given alongside ``--figure``).

    Recently edited figures may be targeted via ``--recent [HOURS]``, which
    selects the figures not in 'stand-by' status whose SVG was modified within
    the given window. It is ignored when ``--figure`` is set.

    In write mode, the confirmation prompt is skipped for batches smaller
    than ``LARGE_BATCH`` (see :meth:`handle_mode` and :meth:`processing`).

    :cvar TITLE: The display title of the script.
    :type TITLE: str
    :cvar LOG_NAME: Standard prefix for logging, specific to the build-images process.
    :type LOG_NAME: str
    :cvar DC_COLLECTIONS: Mapping of collection names to their file prefix representations.
    :type DC_COLLECTIONS: dict
    :cvar RECENT_HOURS: Default time window, in hours, used by ``--recent``.
    :type RECENT_HOURS: int
    :cvar LARGE_BATCH: Minimum batch size that requires write confirmation.
    :type LARGE_BATCH: int

    :ivar collection: The specific figure collection targeted for processing (defaults to "all").
    :vartype collection: str
    :ivar figure: The label of a single figure to build (e.g. "C01-mtx-hydro"), or None.
    :vartype figure: str or None
    :ivar recent: The ``--recent`` time window in hours, or None when not requested.
    :vartype recent: float or None
    :ivar write_confirmed: True once write mode has been confirmed in this run.
    :vartype write_confirmed: bool
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

    RECENT_HOURS = 24
    LARGE_BATCH = 3

    def __init__(self):
        super().__init__()
        self.collection = None
        self.figure = None
        self.recent = None
        self.write_confirmed = False

    def get_parser(self):
        parser = super().get_parser()

        parser.add_argument("--collection", default="all", help="Collection")
        parser.add_argument(
            "--figure",
            default=None,
            help=(
                "Build a single figure by its label (e.g. 'C01-mtx-hydro'). "
                "The chapter is inferred from the label's leading 'C<nn>' "
                "token, so --collection is ignored when this is set."
            ),
        )
        parser.add_argument(
            "--recent",
            nargs="?",
            type=float,
            const=self.RECENT_HOURS,
            default=None,
            metavar="HOURS",
            help=(
                "Build only figures not in 'stand-by' status whose SVG was "
                f"modified in the last HOURS hours (default: {self.RECENT_HOURS}). "
                "Ignored when --figure is set."
            ),
        )

        return parser

    def set_arguments(self, args):
        super().set_arguments(args)
        self.collection = args.collection
        self.figure = args.figure
        self.recent = args.recent

        # Script.run() reads args.chapter right after this method returns,
        # via the same Namespace object, and crashes if it's None. A
        # --figure label already encodes its chapter (e.g. "C01-mtx-hydro"
        # -> chapter 1), so fill it in here unless the user passed
        # --chapter explicitly.
        if self.figure and not args.chapter:
            args.chapter = self.get_chapter_from_label(self.figure)

    def handle_mode(self, mode):
        """
        Defers the write confirmation until the batch size is known.

        In write mode, prints the mode banner without asking; the prompt is
        issued later in :meth:`processing`. Safe mode is delegated to
        :meth:`Script.handle_mode` unchanged.

        :param mode: True if ``-w`` was passed.
        :type mode: bool
        :returns: 0 in write mode, otherwise the parent's return value.
        :rtype: int
        """
        if not mode:
            return super().handle_mode(mode)

        print("\n\n")
        print(80 * "=")
        print("WRITING MODE")
        self.print_info(
            f"confirmation deferred (asked only for batches of {self.LARGE_BATCH}+ figures)"
        )
        self.write = True
        return 0

    @staticmethod
    def get_chapter_from_label(label):
        """
        Extracts the chapter number encoded in a figure label.

        Figure labels follow the pattern ``C<chapter>-<collection>-<name>``,
        e.g. ``"C01-mtx-hydro"`` encodes chapter 1. This parses the leading
        ``C``-prefixed token and returns it as an integer.

        :param label: The figure label (e.g. ``"C01-mtx-hydro"``).
        :type label: str
        :returns: The chapter number.
        :rtype: int
        """
        token = label.split("-")[0]
        return int(token.lstrip("Cc"))

    def is_recent_svg(self, note_file):
        """
        Checks if a note's paired SVG was modified within ``self.recent`` hours.

        :param note_file: Path to the figure's markdown note.
        :type note_file: str or pathlib.Path
        :returns: True if the SVG exists and is within the window, False otherwise.
        :rtype: bool
        """
        f = Path(note_file)
        fsvg = f.parent / f"{f.stem}.svg"

        if not fsvg.is_file():
            return False

        return time.time() - fsvg.stat().st_mtime <= self.recent * 3600

    def processing(self):
        """
        Executes the main figure rendering workflow.

        When ``self.figure`` is set, targets a single note directly (its
        chapter, already resolved onto ``self.current_chapter`` in
        :meth:`set_arguments`, comes from the label) and skips status
        filtering, since an explicitly named figure should be built
        regardless of its 'concluded'/'pending' status. Otherwise, discovers
        notes for the current chapter and chosen collection, loads them into
        a metadata catalog, filters by status, and iterates over the
        filtered list to export the associated SVG files into raster
        images. When ``self.recent`` is set, the status filter is replaced
        by 'not stand-by' plus an SVG modification time check. In write
        mode, batches of ``LARGE_BATCH`` or more figures ask for confirmation
        once per run before rendering; declining switches to safe mode.
        Finally, it triggers the distribution of the files built in this run
        to the target drive.

        :returns: None
        """
        c_n = self.current_chapter

        self.set_src_dir(c_n=c_n)

        nc = NoteCollFigure()

        # --------------------------------------------------
        # Discover notes
        # --------------------------------------------------

        chn = self.get_chapter_folder_name(c_n)

        if self.figure:
            ls_notes = list(FIGURES_DIR.glob(f"./{chn}/{self.figure}.md"))
        else:
            col = self.DC_COLLECTIONS[self.collection]
            ls_notes = list(FIGURES_DIR.glob(f"./{chn}/C*-{col}-*.md"))

        if len(ls_notes) == 0:
            if self.figure:
                self.print_warn(f"WARNING >>> figure '{self.figure}' not found")
            else:
                self.print_warn("WARNING >>> 0 notes found")
            return None

        # --------------------------------------------------
        # Load with progress bar
        # --------------------------------------------------
        # heading_subsection(msg="Load data")
        self.print_info("loading data ...")
        with tqdm(ls_notes, desc=" >>> ", unit="file", bar_format=PBAR_FORMAT) as pbar:
            nc.load_list(pbar)

        s = get_message(f"{len(ls_notes)} notes loaded to collection.")
        self.print_info(s)

        # --------------------------------------------------
        # Work dataframe
        # --------------------------------------------------
        # heading_subsection(msg="Filter data")
        self.print_info(f"filtering data ...")

        df_full = nc.catalog.copy()

        if self.figure:
            # a single figure was explicitly requested — build it regardless
            # of its concluded/pending status
            df = df_full.copy()
        elif self.recent is not None:
            df = df_full.query("status != 'stand-by'").copy()
            is_recent = df["note_file"].apply(self.is_recent_svg).astype(bool)
            df = df[is_recent].reset_index(drop=True)
        else:
            df = df_full.copy()
            df_sub_1 = df.query("status == 'concluded'").copy()
            df_sub_2 = df[df["status"].str.contains("pending", na=False)]

            df = pd.concat([df_sub_1, df_sub_2]).reset_index(drop=True)

        self.print_info(f"{len(df)} notes filtered.")

        if self.recent is not None and not self.figure and len(df) == 0:
            self.print_warn(
                f"WARNING >>> 0 figures modified in the last {self.recent:g} hours"
            )
            return None

        print("\n")
        print(df[["note_name", "title"]])
        print("\n")

        # --------------------------------------------------
        # Write gate (large batches only)
        # --------------------------------------------------
        if self.write and not self.write_confirmed and len(df) >= self.LARGE_BATCH:
            if self.gate_keeper("This script will overwrite data\n"):
                self.print_step("Writing confirmed (write mode)")
                self.write_confirmed = True
            else:
                self.print_warn("Writing cancelled (entering safe mode)")
                self.write = False

        # --------------------------------------------------
        # Process
        # --------------------------------------------------
        # heading_subsection(msg="Render SVG")
        ls_skipped = []
        ls_failed = []
        ls_built = []
        self.print_info(f"rendering SVGs ...")
        for _, row in tqdm(df.iterrows(), total=len(df), desc=" >>> ", unit="file", bar_format=PBAR_FORMAT):

            f = Path(row["note_file"])
            fig_name = f.stem

            if fig_name in config.get("skip_figs", []) and not self.figure:
                ls_skipped.append(fig_name)
                continue

            try:
                fsvg = f.parent / f"{fig_name}.svg"

                if not fsvg.is_file():
                    continue

                svg = FigureSVG()
                svg.load_data(fsvg)

                if self.write:

                    # PDF building
                    self.build_pdf(f.stem, svg, row, opacity=0)

                    # JPEG building
                    self.build_image(
                        f.stem,
                        svg,
                        row,
                        build_jpeg=True,
                        delete_png=True,
                        opacity=1,
                    )

                    if row["collection"] == "box":

                        # JPEG + PNG building
                        self.build_image(
                            f.stem,
                            svg,
                            row,
                            build_jpeg=False,
                            delete_png=False,
                            opacity=0,
                        )

                else:
                    time.sleep(0.01)

                ls_built.append(fig_name)

            except Exception as e:
                ls_failed.append((fig_name, str(e)))

        self.send_to_drive(ls_names=ls_built)

        if ls_skipped:
            self.print_warn(msg="Some figures were skipped (hard-coded list):")
            pprint.pp(ls_skipped)

        if ls_failed:
            self.print_warn(msg="Some figures failed to build:")
            for name, err in ls_failed:
                self.print_warn(f"  {name}: {err}")

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

    def send_to_drive(self, ls_names=None):
        """
        Distributes generated images to their final chapter directories.

        Scans the standard output directory for newly created T1
        files, and copies them to the respective ``FIGURES_DIR/chapterXX/T1``
        folders based on the prefixes of the filenames. Respects safe execution
        mode by simulating the copy process if ``self.write`` is False.

        :param ls_names: Figure names to send (e.g. ``["C01-mtx-hydro"]``). If None, sends every T1 file found.
        :type ls_names: list of str or None
        :returns: None
        """
        folder = STD_OUTPUT
        ls_figs_jpeg = glob.glob(f"{folder}/C*_T1.jpeg")
        ls_figs_png = glob.glob(f"{folder}/C*_T1.png")
        ls_figs_pdf = glob.glob(f"{folder}/C*_T1.pdf")
        ls_figs = ls_figs_jpeg + ls_figs_png + ls_figs_pdf

        if ls_names is not None:
            ls_stems = [f"{name}_T1" for name in ls_names]
            ls_figs = [f for f in ls_figs if Path(f).stem in ls_stems]

        self.print_info("sending from outputs to drive")

        for f in tqdm(ls_figs, desc=" >>> ", unit="file", bar_format=PBAR_FORMAT):
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