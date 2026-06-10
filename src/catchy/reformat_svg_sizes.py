"""
Head docs
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

DC_NEW_WIDTHS = {
    "L": str(172),
    "M": str(126),
    "S": str(83.5)
}


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
        counter = 0

        self.print_info(f"processing data")
        for _, row in tqdm(df.iterrows(), total=len(df), desc=" >>> ", unit="files"):
        #for row in df.to_dict(orient='records'):
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
            #pprint.pp(dc_elements)

            for k in list(DC_NEW_WIDTHS.keys()):
                if k in dc_elements:
                    fig.set_property(element=dc_elements[k]["element"], key="width", value=DC_NEW_WIDTHS[k])

            fig.save()
            counter += 1

        self.print_info(f"{counter} notes reformatted for sizes.")
        self.print_step("Done")
        return None


if __name__ == "__main__":

    s = ScriptReformatFonts()
    s.run()