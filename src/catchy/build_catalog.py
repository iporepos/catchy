"""
ScriptBuildCatalog — LaTeX Figure Catalog Generator
====================================================
Builds a per-chapter LaTeX catalog document from figure note metadata,
combining a status-report table with individual per-figure TeX entries
generated from a shared template. Also mirrors figure image files into the
catalog directory tree for standalone compilation, writes a JSON sidecar
with the same figure/image metadata for a website mirror of the PDF
catalog, and -- once all chapters are processed -- merges every chapter's
JSON sidecar into a single catalog.json list alongside main.tex.

Subclasses :class:`losalamos.tools.core.Script`, inheriting CLI argument
parsing (``--chapter``, ``--write``), safe/write mode gating with user
confirmation, standard console logging (INFO / STEP / WARN), and chapter
iteration over the range defined in ``config.local.json``.

Usage
-----
    python build_catalog.py --chapter <N|all> [-w] [--compile]

Arguments
---------
    --chapter       Chapter number to process, or ``all`` to iterate over
                    [CHAPTER_START, CHAPTER_END] as set in config.local.json.
                    Inherited from Script.get_parser().
    -w / --write    Enable write mode. Without this flag, figure TeX files
                    are processed but never written (safe mode sleeps 20 ms
                    per figure to simulate work). With it, a confirmation
                    prompt is shown before any files are touched.
    --compile       Compile the merged catalog TeX (DOCUMENTS_DIR /
                    catalog/main.tex) into a PDF at the end of run(), via
                    DocumentTeX.to_pdf(). Without this flag, per-chapter
                    .tex/.json generation still happens as usual -- only
                    the PDF build (and main.pdf -> catalog.pdf rename) is
                    skipped. Added in get_parser(); read back off
                    self.compile in run().

Behaviour (per chapter)
-----------------------
    1. Globs FIGURES_DIR / chapter<NN> / C*-*-*.md and loads all notes
       into a NoteCollFigure collection.
    2. Splits notes into four sub-DataFrames by collection (cover, main
       text, biography, box), sorts each by order, then concatenates them
       in that display order.
    3. Generates per-figure TeX entries (generate_figure_tex):
           - Loads _catalog_figure.tex from FOLDER_TEMPLATES_DOCUMENTS.
           - Substitutes [[placeholder]] tokens with derived field values
             (title, label, file paths, caption, category, credits, width,
             status, etc.).
           - Writes one .tex file per figure to STD_OUTPUT (write mode only),
             then copies each to FIGURES_DIR / chapter<NN>/ via
             send_figures_tex().
    4. Generates a LaTeX status-report table (generate_table_tex) using
       pandas.DataFrame.to_latex(), wrapping it in \\scriptsize/\\sffamily
       and prefixing a bold chapter heading.
    5. Merges the table and all per-figure TeX entries into a single chapter
       file at DOCUMENTS_DIR / catalog/chapters/chapter<NN>.tex
       (generate_chapter_tex).
    6. Builds a JSON sidecar for the chapter (generate_figure_json /
       generate_chapter_json), mirroring the figure and image metadata for
       a website version of the catalog. Written to
       DOCUMENTS_DIR / catalog/chapters/chapter<NN>.json alongside the .tex
       file, regardless of write mode (same as the merged .tex file, since
       it only reads data already loaded into df — no bulk file writes are
       involved). This is a first pass; see Notes below.
    7. Copies T0 and T1 JPEG/PNG figure images into
       DOCUMENTS_DIR / catalog/figs/chapter<NN>/T0|T1/ for standalone
       catalog compilation (copy_figures_to_chapter).

Post-processing (run(), after all chapters)
--------------------------------------------
    1. merge_chapter_json(): globs every chapter<NN>.json currently on disk
       under catalog/chapters/ -- not just the chapter(s) touched by this
       particular run -- and writes them as a single JSON list to
       DOCUMENTS_DIR / catalog/catalog.json, alongside main.tex. Runs
       unconditionally, independent of --write / --compile. The list order
       is whatever glob/sort gives us -- it does NOT read each chapter's
       own metadata.order to sort itself; that's on the consumer for now.
    2. Only if --compile was passed: compiles catalog/main.tex to PDF via
       DocumentTeX.to_pdf() and renames main.pdf -> catalog.pdf. Skipped
       entirely otherwise.

Field derivation helpers
------------------------
    get_status_mvp   LimeGreen=concluded, YellowOrange=pending,
                     RedOrange=untouched (stand-by), Gray=undefined.
                     Any status containing 'ftp' is treated as concluded.
    get_status_ftp   Concluded/pending only within 'ftp'-tagged statuses;
                     all others render as Gray/undefined.
    get_status_plain Plain-text (non-LaTeX) counterpart of get_status_mvp /
                     get_status_ftp / the always-concluded draft tier, for
                     the JSON sidecar's per-image "status" field.
    get_file_path    Constructs the relative image path for T0/T1 tiers;
                     T1 path falls back to 'example-image' for stand-by notes.
    get_file_path_json  Plain-path counterpart of get_file_path for the JSON
                     sidecar: returns None instead of the 'example-image'
                     LaTeX placeholder when a tier has no real file.
    get_width        Maps size codes (XS/S/M/L/XL) to mm values
                     (30/81/120/170/210 mm); undefined renders as highlighted.
    get_width_print  Clamps XL (210 mm) to 170 mm for print layout; inherits
                     120 mm fallback for undefined sizes.
    get_width_plain  Plain-text counterpart of get_width for the JSON
                     sidecar: same mm string, but None (instead of a LaTeX
                     colorbox) when the note has no size code.
    get_credits      Handles three cases: "The Authors" (verbatim),
                     "on credits" (reads a # Credits section from the note
                     body via get_credits_from_data), or a literal source
                     string. All URLs are wrapped with latexify_urls(). No
                     source (or an empty # Credits section) returns the
                     bare undefined colorbox, with no "The Authors, based
                     on:" prefix.
    get_credits_plain  Plain-text counterpart of get_credits for the JSON
                     sidecar: same three-case logic, but no \\url{} wrapping
                     and a plain "The Authors, based on: " prefix; returns
                     None when there's no source or no # Credits section.
    get_credits_from_data  Now takes an optional `sep` (default the existing
                     LaTeX line break " \\ ") so get_credits_plain can join
                     body lines with "\n" instead for the JSON sidecar.
    get_caption      Escapes %, _, #, ^ and strips non-ASCII before output.
    get_comment      Same sanitisation as caption; replaces >>> markers.

Module-level utilities
----------------------
    latexify_urls(text)      Wraps bare http/https URLs in \\url{}, stripping
                             trailing punctuation (.,);:) before wrapping.
    remove_non_ascii(text)   Strips all non-ASCII characters via ASCII
                             encode/decode round-trip.
    collapse_whitespace(text)  Replaces \\n / \\r\\n artifacts with spaces and
                             collapses repeated whitespace to one space.
                             Applied to caption/notes/credits in
                             generate_figure_json so long free-text fields
                             stay single-line in the JSON sidecar.

Key paths (resolved from config.local.json at import time)
-----------------------------------------------------------
    Notes root:      FIGURES_DIR / chapter<NN>/  (BASE_DIR / "figures/main")
    Template:        FOLDER_TEMPLATES_DOCUMENTS / "_catalog_figure.tex"
    Figure TeX out:  STD_OUTPUT / <name>.tex  (per figure, then copied)
    Chapter TeX out: DOCUMENTS_DIR / catalog/chapters/chapter<NN>.tex
    Chapter JSON out: DOCUMENTS_DIR / catalog/chapters/chapter<NN>.json
    Chapters metadata in: DOCUMENTS_DIR / catalog/chapters_metadata.json
                       (hand-maintained, keyed by label -- see Notes)
    Catalog JSON out: DOCUMENTS_DIR / catalog/catalog.json  (merge of all
                       chapter<NN>.json, built once in run() via
                       merge_chapter_json())
    Image mirror:    DOCUMENTS_DIR / catalog/figs/chapter<NN>/T0|T1/

Dependencies
------------
    losalamos.notes         NoteCollFigure, NoteFigure
    losalamos.paths         FOLDER_TEMPLATES_DOCUMENTS
    losalamos.tools.core    Script, LOG_PREFIX, NOTE_PATTERN,
                            FIGURES_DIR, DOCUMENTS_DIR, STD_OUTPUT
    catchy.core             (project-level utilities)
    pandas                  DataFrame construction and to_latex() export
    json                    JSON sidecar serialisation

Notes
-----
    - The [[placeholder]] substitution in generate_figure_tex is a simple
      str.replace pass over the template; token collisions between field
      values and other tokens are not guarded against.
    - send_figures_tex derives the destination chapter folder from the figure
      filename prefix (C<NN>-…), so filenames must follow the C<NN>-<col>-<name>
      convention to route correctly.
    - copy_figures_to_chapter always runs regardless of write mode, since it
      operates on already-published image files rather than note data.
    - Non-ASCII stripping in get_comment/get_caption is lossy; characters with
      diacritics (accented author names, etc.) will be silently dropped. The
      JSON sidecar deliberately does NOT reuse get_caption/get_comment for
      this reason — it pulls caption/title/category/notes straight off the
      row (get_*_plain helpers) so the website copy keeps accents intact.
      "notes" is a light-touch mirror of the note's raw comment field
      (quote-stripped only) — it does not apply get_comment's >>> / LaTeX
      character cleanup, so review it against real note bodies once you
      have data with those markers in it.
    - Chapter-level metadata (title/subtitle/abstract/collection) is looked
      up from an external, hand-maintained JSON file at
      get_chapters_metadata_path() (default DOCUMENTS_DIR /
      catalog/chapters_metadata.json), keyed by chapter label ("chapter00",
      "chapter01", ...). See generate_chapter_json / load_chapters_metadata.
      Missing file -> a warning is printed once and every chapter falls
      back to {"order": self.current_chapter, everything else: None}.
      Missing entry for a given label -> same per-field fallback. The
      lookup is cached on the instance after the first read (_chapters_metadata),
      so one file read serves every chapter in a --chapter all run.
    - JSON sidecar is a first pass: the Fine-Tuned Product image has no tier
      mirrored to disk anywhere in this pipeline yet, so its "file" is
      always null and its "status" falls back to "stand-by" when the note's
      raw status isn't ftp-tagged (get_status_plain's "ftp" branch). Flagged
      for a later iteration once that data exists.
"""

import pprint
import shutil
import time
import re
import json

# external
from tqdm import tqdm
import pandas as pd

from losalamos.notes import NoteCollFigure
from losalamos.documents import DocumentTeX
from losalamos.paths import FOLDER_TEMPLATES_DOCUMENTS
from losalamos.tools.core import *

# local
from catchy.core import *

URL_PATTERN = re.compile(r"(https?://[^\s\\]+)", flags=re.IGNORECASE)


def latexify_urls(text: str) -> str:

    def replacer(match):
        url = match.group(0)

        # Strip trailing punctuation
        trailing = ""
        while url[-1] in ".,);:":
            trailing = url[-1] + trailing
            url = url[:-1]

        return r"\url{" + url + "}" + trailing

    return URL_PATTERN.sub(replacer, text)


def remove_non_ascii(text: str) -> str:
    return text.encode("ascii", "ignore").decode("ascii")


def collapse_whitespace(text):
    """Replaces newline/carriage-return artifacts with spaces and collapses
    runs of whitespace to a single space, for long free-text fields
    (caption/notes/credits) headed into the JSON sidecar, where an embedded
    line break can trip up downstream (JS string handling, CSV re-export,
    etc.). Returns None unchanged (nothing to clean)."""
    if text is None:
        return None
    s = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


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

        # Discover notes
        # --------------------------------------------------

        chn = self.get_chapter_folder_name(c_n)
        ls_notes = list(FIGURES_DIR.glob(f"./{chn}/C*-*-*.md"))

        if len(ls_notes) == 0:
            self.print_warn("WARNING >>> 0 notes found")
            return None

        # Load
        # --------------------------------------------------

        self.print_info(f"{chn} -- loading data ...")
        with tqdm(ls_notes, desc=" >>> ", unit="file") as pbar:
            nc.load_list(pbar)

        s = get_message(f"{chn} -- {len(ls_notes)} notes loaded")
        self.print_info(s)

        df_full = nc.catalog.copy()
        df_full["order"] = df_full["order"].astype(int)

        # Work DataFrame
        # --------------------------------------------------

        df_bio = df_full.query("collection == 'biography'").copy()
        df_box = df_full.query("collection == 'box'").copy()
        df_mtx = df_full.query("collection == 'main text'").copy()
        df_cov = df_full.query("collection == 'cover'").copy()

        df_bio = df_bio.sort_values(by="order").reset_index(drop=True)
        df_box = df_box.sort_values(by="order").reset_index(drop=True)
        df_mtx = df_mtx.sort_values(by="order").reset_index(drop=True)
        df_cov = df_cov.sort_values(by="order").reset_index(drop=True)

        df = pd.concat([df_cov, df_mtx, df_bio, df_box]).reset_index(drop=True)

        print("\n")
        print(df[["collection", "title", "category", "note_name", "status", "size"]])
        print("\n")

        # Process
        # --------------------------------------------------
        self.print_info(f"{chn} -- generating catalog ...")

        # load template
        self.print_info(f"{chn} -- loading template ...")
        f_template = FOLDER_TEMPLATES_DOCUMENTS / "tex/_catalog_figure.tex"

        with f_template.open("r", encoding="utf-8") as f:
            content = f.read()

        # handle figures
        # --------------------------------------------------
        self.print_info(f"{chn} -- handling figures ...")
        ls_tex_figures = self.generate_figure_tex(df=df, template=content)

        # send figures
        # --------------------------------------------------
        self.print_info(f"{chn} -- sending to chapter folder ...")
        ls_tex_figures = self.send_figures_tex(ls_tex_figures)

        # merge
        # --------------------------------------------------
        self.print_info(f"{chn} -- merging ...")
        # generate tex table
        tab = self.generate_table_tex(df)
        fo = self.generate_chapter_tex(ls_tex_figures, tab)
        self.print_info(f"{chn} -- merged: {fo}")

        # json sidecar
        # --------------------------------------------------
        self.print_info(f"{chn} -- building json sidecar ...")
        ls_figures_json = self.generate_figure_json(df)
        fo_json = self.generate_chapter_json(ls_figures_json)
        self.print_info(f"{chn} -- json sidecar: {fo_json}")

        # copy
        # --------------------------------------------------
        self.copy_figures_to_chapter()

    def generate_chapter_tex(self, ls_figs, table):

        paths = [Path(f) for f in ls_figs]

        chn = self.get_chapter_folder_name(self.current_chapter)
        dst_dir = DOCUMENTS_DIR / f"catalog/chapters"
        dst_dir.mkdir(exist_ok=True)
        output = dst_dir / f"{chn}.tex"

        with open(output, "w", encoding="utf-8") as outfile:
            outfile.write("\n\n")
            outfile.write(f"% Start of {chn} \n")
            outfile.write(f"% -----------------------------\n")
            outfile.write(table)
            for i, path in enumerate(paths):
                with open(path, "r", encoding="utf-8") as infile:
                    content = infile.read()
                    # Write the content
                    outfile.write("\n\n")
                    outfile.write(f"% Start of {path.name} \n")
                    outfile.write(f"% -----------------------------\n")
                    outfile.write(content)
                    outfile.write("\n\n")

        return output

    def get_chapters_metadata_path(self):
        return DOCUMENTS_DIR / "catalog/chapters_metadata.json"

    def load_chapters_metadata(self):
        if getattr(self, "_chapters_metadata", None) is None:
            fp = self.get_chapters_metadata_path()
            if fp.exists():
                with open(fp, "r", encoding="utf-8") as f:
                    self._chapters_metadata = json.load(f)
            else:
                self.print_warn(
                    f"WARNING >>> chapters metadata file not found: {fp}"
                )
                self._chapters_metadata = {}

        return self._chapters_metadata

    def generate_chapter_json(self, ls_figures):
        chn = self.get_chapter_folder_name(self.current_chapter)
        dst_dir = DOCUMENTS_DIR / f"catalog/chapters"
        dst_dir.mkdir(exist_ok=True)
        output = dst_dir / f"{chn}.json"

        dc_chapters_meta = self.load_chapters_metadata()
        dc_this = dc_chapters_meta.get(chn, {})

        dc_chapter = {
            "metadata": {
                "label": chn,
                "order": dc_this.get("order", self.current_chapter),
                "title": dc_this.get("title"),
                "subtitle": dc_this.get("subtitle"),
                "abstract": dc_this.get("abstract"),
                "collection": dc_this.get("collection"),
            },
            "figures": ls_figures,
        }

        with open(output, "w", encoding="utf-8") as f:
            json.dump(dc_chapter, f, indent=2, ensure_ascii=False)

        return output

    def generate_table_tex(self, df):
        chnm = "Chapter " + str(self.current_chapter)
        df_entry = df[
            ["collection", "title", "category", "note_name", "status", "size"]
        ].copy()

        ls_title = list()
        ls_category = list()
        ls_files = list()
        ls_status = list()
        ls_size = list()

        for _, row in tqdm(
            df_entry.iterrows(),
            total=len(df),
            desc=" >>> ",
            unit="file",
        ):
            ls_category.append(self.get_category(row))
            ls_files.append(self.get_file_texttt(row))
            ls_status.append(self.get_status_mvp(row))
            ls_size.append(self.get_width(row))

            s = row.get("note_name").replace('"', "")
            s2 = r"\nameref{sec_" + s + "}"
            ls_title.append(s2)

        dc = {
            "Title": ls_title,
            "Category": ls_category,
            "Width": ls_size,
            "File": ls_files,
            "Status MVP": ls_status,
        }
        df = pd.DataFrame(dc)
        df["Collection"] = df_entry["collection"]
        df["Chapter"] = chnm
        df["N"] = df.index + 1
        df = df[
            [
                "N",
                "Chapter",
                "Title",
                "File",
                "Collection",
                "Category",
                "Width",
                "Status MVP",
            ]
        ].copy()

        s = df.to_latex(
            index=False,
            caption=(f"Status Report of {chnm}", f"Status Report of {chnm}"),
            column_format="llllllll",
            label="",
        )

        # Wrapping the output in a specific size
        new = "\\begin{table}[h!] \n \\scriptsize \n \\sffamily"
        table_s = s.replace(r"\begin{table}", new)

        s1 = r"\noindent \textbf{Status report}: " + chnm + r" \\ " + "\n"
        s1 = s1 + r"\noindent \\" + "\n"
        r"""
        s1 = s1 + r"\noindent \small \textbf{Concluded}: \\" + "\n"
        s1 = s1 + r"\noindent \small \textbf{Pending}: \\" + "\n"
        s1 = s1 + r"\noindent \small \textbf{Untouched}: \\" + "\n"
        """
        final_output = (
            s1 + "\n" + table_s + "\n" + r"\vspace{5cm}" + "\n" + r"\clearpage"
        )

        return final_output

    def generate_figure_tex(self, df, template):
        ls_tex_figures = list()
        for _, row in tqdm(
            df.iterrows(),
            total=len(df),
            desc=" >>> ",
            unit="file",
        ):
            content_print = template[:]

            nm = row.get("name", "unknown").replace('"', "")

            dc = {}

            dc["[[title]]"] = row.get("title", "untitled").replace('"', "")
            dc["[[label]]"] = nm
            dc["[[file_mvp]]"] = self.get_file_path(row, tier="T1")
            dc["[[file_draft]]"] = self.get_file_path(row, tier="T0")
            dc["[[file]]"] = self.get_file_texttt(row)
            dc["[[collection]]"] = row.get("collection", "unknown").replace('"', "")
            dc["[[caption]]"] = self.get_caption(row)
            dc["[[category]]"] = self.get_category(row)
            dc["[[chapter]]"] = self.get_chapter(row)
            dc["[[comment]]"] = self.get_comment(row)
            dc["[[credits]]"] = self.get_credits(row)
            dc["[[width]]"] = self.get_width(row)
            dc["[[width_print]]"] = self.get_width_print(row)
            dc["[[status_mvp]]"] = self.get_status_mvp(row)
            dc["[[status_ftp]]"] = self.get_status_ftp(row)

            # pprint.pp(dc)

            for k in dc:
                content_print = content_print.replace(k, dc[k])

            if self.write:
                nm = row["name"].replace('"', "")
                fo = STD_OUTPUT / f"{nm}.tex"
                fo.write_text(content_print, encoding="utf-8")
                ls_tex_figures.append(fo)
            else:
                time.sleep(0.02)

        return ls_tex_figures

    def generate_figure_json(self, df):
        ls_figures = list()

        for _, row in tqdm(
            df.iterrows(),
            total=len(df),
            desc=" >>> ",
            unit="file",
        ):
            nm = str(row.get("name", "unknown")).replace('"', "")

            title = row.get("title")
            title = (
                None
                if title is None or isinstance(title, float)
                else str(title).replace('"', "")
            )

            caption = row.get("caption")
            caption = (
                None
                if caption is None or isinstance(caption, float)
                else str(caption).replace('"', "")
            )

            category = row.get("category")
            category = (
                None
                if category is None or isinstance(category, float)
                else str(category).replace('"', "")
            )

            order = row.get("order")
            order = None if order is None else int(order)

            width = self.get_width_plain(row)

            comment = row.get("comment")
            comment = (
                None
                if comment is None or isinstance(comment, float)
                else collapse_whitespace(str(comment).replace('"', ""))
            )

            caption = collapse_whitespace(caption)

            credits = self.get_credits_plain(row)
            credits = collapse_whitespace(credits)

            dc_metadata = {
                "label": nm,
                "order": order,
                "title": title,
                "width": width,
                "category": category,
                "collection": str(row.get("collection", "unknown")).replace('"', ""),
                "caption": caption,
                "notes": comment,
                "credits": credits,
            }

            dc_images = [
                {
                    "tier": 0,
                    "name": "Draft",
                    "status": self.get_status_plain(row, kind="draft"),
                    "file": self.get_file_path_json(row, tier="T0"),
                },
                {
                    "tier": 1,
                    "name": "Minimum Viable Product",
                    "status": self.get_status_plain(row, kind="mvp"),
                    "file": self.get_file_path_json(row, tier="T1"),
                },
                {
                    "tier": 2,
                    "name": "Fine-Tuned Product",
                    "status": self.get_status_plain(row, kind="ftp"),
                    "file": None,  # FTP tier is not mirrored to disk yet
                },
            ]

            ls_figures.append({"metadata": dc_metadata, "images": dc_images})

        return ls_figures

    def send_figures_tex(self, ls_figs):
        ls = list()

        if len(ls_figs) == 0:
            return ls
        else:
            for f_src in tqdm(ls_figs, desc=" sending ", unit="file"):
                fp = Path(f_src)
                nm = fp.name
                chn = "chapter" + nm.split("-")[0].replace("C", "")
                f_dst = FIGURES_DIR / f"{chn}/{nm}"
                shutil.copy(src=f_src, dst=f_dst)
                ls.append(f_dst)

        return ls

    def copy_figures_to_chapter(self):

        chn = self.get_chapter_folder_name(self.current_chapter)
        dst_dir = DOCUMENTS_DIR / f"catalog/figs/{chn}"

        src_dir = FIGURES_DIR / f"{chn}"

        ls_tiers = ["T0", "T1"]

        for d in ls_tiers:
            src_dir_tier = src_dir / d

            dst_dir_tier = dst_dir / d
            dst_dir_tier.mkdir(exist_ok=True)

            ls_src_files = list(src_dir_tier.glob("C*-*-*.jpeg"))

            self.print_info(f"copying files to {d} ...")
            for f in tqdm(ls_src_files, desc=" copying ", unit="file"):
                f_dst = dst_dir_tier / f.name
                shutil.copy(src=f, dst=f_dst)

        return None

    def get_status_mvp(self, dc):
        s = dc.get("status", "stand-by")
        sts = ""

        if "ftp" in s:
            return r"\colorbox{LimeGreen}{concluded}"

        if s == "concluded":
            sts = r"\colorbox{LimeGreen}{concluded}"
        elif "pending" in s:
            sts = r"\colorbox{YellowOrange}{" + s + "}"
        elif s == "stand-by":
            sts = r"\colorbox{RedOrange}{untouched}"
        else:
            sts = r"\colorbox{Gray}{undefined}"

        return sts

    def get_status_ftp(self, dc):
        s = dc.get("status", "stand-by")
        sts = ""

        if "ftp" in s:
            if "concluded" in s:
                sts = r"\colorbox{LimeGreen}{concluded}"

            if "pending" in s:
                sts = r"\colorbox{YellowOrange}{" + s + "}"

        else:
            sts = r"\colorbox{Gray}{undefined}"

        return sts

    def get_status_plain(self, dc, kind="mvp"):
        s = dc.get("status", "stand-by")

        if kind == "draft":
            # T0 is produced for every note regardless of status, so it is
            # always considered available/concluded
            return "concluded"

        if kind == "mvp":
            if "ftp" in s:
                return "concluded"
            if s == "concluded":
                return "concluded"
            if "pending" in s:
                return s
            if s == "stand-by":
                return "stand-by"
            return "undefined"

        if kind == "ftp":
            # NOTE: unlike get_status_ftp's LaTeX version (which renders
            # non-ftp-tagged notes as "undefined"/Gray), this plain version
            # falls back to "stand-by" for the website, since there is no
            # FTP tier on disk yet either way -- flag for review.
            if "ftp" in s:
                if "concluded" in s:
                    return "concluded"
                if "pending" in s:
                    return s
            return "stand-by"

        return "undefined"

    def get_file_path(self, dc, tier="T1"):
        sts = dc.get("status", "stand-by")
        fp = "example-image"
        s = dc.get("name").replace('"', "")
        cn = s.split("-")[0].replace("C", "")
        f = self.get_file(dc)
        f = f.replace(".", f"_{tier}.")
        fp_default = f"figs/chapter{cn}/{tier}/{f}"
        if tier == "T1":
            if sts != "stand-by":
                fp = fp_default
        else:
            fp = fp_default

        fp = fp.replace("png", "jpeg")
        return fp

    def get_file_path_json(self, dc, tier="T1"):
        fp = self.get_file_path(dc, tier=tier)
        if fp == "example-image":
            return None
        return f"./{fp}"

    def get_file(self, dc):
        s = dc.get("note_name").replace('"', "")
        nm = s.split("-")[0].replace("C", "")
        collection = dc.get("collection")
        suff = "jpeg"
        if collection == "box":
            suff = "png"
        f = f"{s}.{suff}"
        return f

    def get_file_texttt(self, dc):
        s = self.get_file(dc)
        s = r"\textbf{" + s + "}"
        s = r"\texttt{" + s + "}"
        return s

    def get_comment(self, dc):
        s = dc.get("comment")
        if s is None or isinstance(s, float):
            s = "No comments found."
        else:
            s = s.replace('"', "")
            s = s.replace(">>>", "")
            s = s.replace("_", " ")
            s = s.replace("^", " ")
            s = s.replace("#", " ")
            s = remove_non_ascii(s)
        return s

    def get_credits(self, dc):

        s = dc.get("source")

        if s is None or isinstance(s, float):
            return r"\colorbox{YellowOrange}{undefined}"
        elif s.replace('"', "").lower() == "the authors":
            return s
        elif s.replace('"', "").lower() == "on credits":
            nm = dc.get("name").replace('"', "")
            cn = nm.split("-")[0].replace("C", "")
            fi = FIGURES_DIR / f"chapter{cn}/{nm}.md"
            s = self.get_credits_from_data(fi)
            if s is None:
                return r"\colorbox{YellowOrange}{undefined}"
        else:
            s = s.replace('"', "")

        s = latexify_urls(s)

        s = r"The Authors, based on: \\ " + s

        return s

    def get_credits_from_data(self, file_note, sep=r" \\ "):
        from losalamos.notes import NoteFigure

        nf = NoteFigure()
        nf.load(file_note=file_note)
        so = None
        b_collect = False
        for line in nf.data["Body"]:
            if b_collect:
                if line.strip() == "":
                    pass
                else:
                    if so is None:
                        so = line[:]
                    else:
                        so = so + sep + line[:]
            if "# Credits" in line:
                b_collect = True
            if "---" in line:
                b_collect = False

        # so2 = r"\begin{verbatim} \\ " + so + r" \\ \end{verbatim}"

        return so

    def get_credits_plain(self, dc):
        s = dc.get("source")

        if s is None or isinstance(s, float):
            return None

        s_clean = str(s).replace('"', "")

        if s_clean.lower() == "the authors":
            return s_clean

        if s_clean.lower() == "on credits":
            nm = str(dc.get("name")).replace('"', "")
            cn = nm.split("-")[0].replace("C", "")
            fi = FIGURES_DIR / f"chapter{cn}/{nm}.md"
            s_clean = self.get_credits_from_data(fi, sep="\n")
            if s_clean is None:
                return None

        return f"The Authors, based on: {s_clean}"

    def get_width(self, dc):

        sz = dc.get("size")
        dc_sizes = {
            "XS": "30 mm",
            "S": "83.5 mm",
            "M": "126 mm",
            "L": "172 mm",
            "XL": "210 mm",
        }
        s = ""
        if sz is None or isinstance(sz, float):
            s = r"\colorbox{YellowOrange}{undefined}"
        else:
            s = dc_sizes[sz]

        return s

    def get_width_print(self, dc):

        s = ""
        w = self.get_width(dc)

        if w == "210 mm":
            s = "172 mm"
        elif w == r"\colorbox{YellowOrange}{undefined}":
            s = "126 mm"
        else:
            s = w

        return s

    def get_width_plain(self, dc):
        sz = dc.get("size")
        dc_sizes = {
            "XS": "30 mm",
            "S": "83.5 mm",
            "M": "126 mm",
            "L": "172 mm",
            "XL": "210 mm",
        }
        if sz is None or isinstance(sz, float):
            return None

        return dc_sizes.get(sz)

    def get_category(self, dc):
        s = dc.get("category")
        if s is None or isinstance(s, float):
            return r"\colorbox{YellowOrange}{undefined}"
        else:
            return str(s).replace('"', "")

    def get_chapter(self, dc):
        nm = dc.get("name").replace('"', "")
        cn = int(nm.split("-")[0].replace("C", ""))
        s = f"Chapter {cn}"
        return s

    def get_caption(self, dc):
        s = dc.get("caption")
        if s is None or isinstance(s, float):
            return r"\colorbox{YellowOrange}{undefined}"
        else:
            s = s.replace('"', "")
            s = s.replace("%", "\\%")
            s = s.replace("_", " ")
            s = s.replace("#", " ")
            s = s.replace("^", " ")
            s = remove_non_ascii(s)
            return s

    def get_parser(self):
        parser = super().get_parser()
        parser.add_argument(
            "--compile",
            action="store_true",
            default=False,
            help="Compile the merged catalog TeX into a PDF after processing "
                 "(tex.to_pdf()). Without this flag, chapter .tex/.json files "
                 "are still generated as usual -- only the PDF build is skipped.",
        )
        return parser

    def merge_chapter_json(self):
        src_dir = DOCUMENTS_DIR / "catalog/chapters"
        ls_files = sorted(src_dir.glob("chapter*.json"))

        ls_chapters = list()
        for f in ls_files:
            with open(f, "r", encoding="utf-8") as infile:
                ls_chapters.append(json.load(infile))

        output = DOCUMENTS_DIR / "catalog/catalog.json"
        with open(output, "w", encoding="utf-8") as outfile:
            json.dump(ls_chapters, outfile, indent=2, ensure_ascii=False)

        return output

    def run(self):
        super().run()

        # json catalog merge
        # --------------------------------------------------
        # Aggregates every chapter<NN>.json currently on disk under
        # catalog/chapters/ -- not just chapters touched by this run -- into
        # a single list at catalog/catalog.json, alongside main.tex. Order
        # is whatever glob/sort gives us for now (chapter attributes/order
        # to be added later).
        self.print_info("merging chapter json files ...")
        fo_json = self.merge_chapter_json()
        self.print_info(f"catalog json merged: {fo_json}")

        if not getattr(self, "compile", False):
            self.print_info("--compile not set -- skipping PDF build")
            return

        # Build TeX document
        MAIN_FILE = DOCUMENTS_DIR / "catalog/main.tex"
        tex = DocumentTeX()
        tex.load_data(MAIN_FILE)
        tex.to_pdf()

        # Rename output file
        MAIN_FILE_PDF = DOCUMENTS_DIR / "catalog/main.pdf"
        MAIN_FILE_PDF_NEW = DOCUMENTS_DIR / "catalog/catalog.pdf"
        if MAIN_FILE_PDF.exists():
            os.rename(MAIN_FILE_PDF, MAIN_FILE_PDF_NEW)



if __name__ == "__main__":

    s = ScriptBuildCatalog()
    s.run()