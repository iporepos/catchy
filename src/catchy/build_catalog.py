import pprint
import shutil
import time
import re

# external
from tqdm import tqdm
import pandas as pd

from losalamos.notes import NoteCollFigure
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
        f_template = FOLDER_TEMPLATES_DOCUMENTS / "_catalog_figure.tex"

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
            s = r"\colorbox{YellowOrange}{undefined}"
        elif s.replace('"', "").lower() == "the authors":
            return s
        elif s.replace('"', "").lower() == "on credits":
            nm = dc.get("name").replace('"', "")
            cn = nm.split("-")[0].replace("C", "")
            fi = FIGURES_DIR / f"chapter{cn}/{nm}.md"
            s = self.get_credits_from_data(fi)
        else:
            s = s.replace('"', "")

        s = latexify_urls(s)

        s = r"The Authors, based on: \\ " + s

        return s

    def get_credits_from_data(self, file_note):
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
                        so = so + r" \\ " + line[:]
            if "# Credits" in line:
                b_collect = True
            if "---" in line:
                b_collect = False

        # so2 = r"\begin{verbatim} \\ " + so + r" \\ \end{verbatim}"

        return so

    def get_width(self, dc):

        sz = dc.get("size")
        dc_sizes = {
            "XS": "30 mm",
            "S": "81 mm",
            "M": "120 mm",
            "L": "170 mm",
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
            s = "170 mm"
        elif w == r"\colorbox{YellowOrange}{undefined}":
            s = "120 mm"
        else:
            s = w

        return s

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


if __name__ == "__main__":

    s = ScriptBuildCatalog()
    s.run()
