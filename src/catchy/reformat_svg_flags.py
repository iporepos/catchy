"""
Reformat SVG Flags
==================

Appends a processing-complete marker to the ``comment`` field of each active
figure note's YAML front-matter, signalling that the SVG has been through the
full reformat pipeline and is ready for fine-tune adjustment.

Architectural context
---------------------
Sits at the end of the SVG reformat pipeline, after
:mod:`reformat_svg_fonts` and :mod:`reformat_svg_sizes`. Subclasses
:class:`catchy.core.Script`, inheriting CLI parsing, write-gate confirmation,
and chapter iteration. Reads and writes Markdown note files directly via
:class:`losalamos.notes.NoteFigure`.

Usage
-----
Run directly::

    python reformat_svg_flags.py --chapter 3
    python reformat_svg_flags.py --chapter all -w

Write mode (``-w``) is required for note saves; omitting it enters safe mode
and no files are touched.

Behaviour
---------
For every active figure note (``C*-*-*.md``, ``status != 'stand-by'``) in the
chapter:

1. **Discover notes** — globs ``FIGURES_DIR/<chapter>/C*-*-*.md`` and loads
   them into a :class:`NoteCollFigure` collection.
2. **Filter** — excludes notes with ``status == 'stand-by'``.
3. **Check flag** — reads the ``comment`` metadata field. If :data:`FLAG`
   is already present, the note is skipped entirely.
4. **Append flag** — concatenates :data:`FLAG` to the existing comment string
   and writes it back to the note's ``comment`` field.
5. **Save** — calls ``NoteFigure.save()`` to persist the updated front-matter.

Module-level constants
----------------------
:data:`FLAG`
    The marker string appended to the ``comment`` field.
    Current value: ``">>> Ipo@2026-06 SVG Reformatted. T2 fine-tune adjust
    margins and symbols"``.

Key paths
---------
* Input / output notes : ``FIGURES_DIR/<chapter>/C*-*-*.md``

Dependencies
------------
* ``losalamos.notes.NoteCollFigure`` — figure note collection loader
* ``losalamos.notes.NoteFigure``     — individual note read/write
* ``catchy.core.Script``             — base class; provides ``--chapter``
                                      CLI, write gate, and ``run()``

Notes
-----
* Re-running is safe: the flag check prevents the marker from being
  appended more than once per note.
* The ``comment`` field is stripped of surrounding double-quotes before
  the flag is appended, then the result is re-quoted when stored.
* Notes with ``status == 'stand-by'`` are silently skipped.
* If zero notes are found for the chapter, the method returns early with
  a warning and no files are touched.
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
        with tqdm(ls_notes, desc=" >>> ", unit="file", bar_format=PBAR_FORMAT) as pbar:
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
        # for _, row in tqdm(df.iterrows(), total=len(df), desc=" >>> ", unit="files"):
        for row in df.to_dict(orient="records"):
            # =============================
            # find note
            n = row["note_name"]
            dc_metadata = nc.collection[n].metadata
            comment = dc_metadata.get("comment", None)

            if comment is None:
                comment = ""

            comment = comment.replace('"', "")

            if FLAG in comment:
                continue

            comment = comment + " " + FLAG
            nc.collection[n].metadata["comment"] = f'"{comment}"'
            nc.collection[n].save()
            counter += 1

        self.print_info(f"{counter} notes flagged.")
        self.print_step("Done")
        return None


if __name__ == "__main__":

    s = ScriptReformatFlags()
    s.run()
