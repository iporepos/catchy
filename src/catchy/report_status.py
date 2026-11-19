"""
ScriptReportStatus — Figure Status Report per Chapter
=====================================================
Read-only progress report over the figure notes. Counts how many figures in
each chapter are concluded, pending, stand-by (or undefined), prints a table
with counts and percentages per chapter plus a TOTAL row, and optionally
saves a 100% stacked bar chart. Its purpose is to show which chapters are
closest to done, without running the catalog pipeline (build_catalog.py).

Subclasses :class:`catchy.core.Script`, inheriting CLI argument parsing
(``--chapter``), standard console logging (INFO / STEP / WARN) and chapter
iteration over the range defined in ``config.local.json``. The write gate is
overridden: this script never writes note data, so it never prompts.

Usage
-----
    python report_status.py [--chapter <N|all>] [--sort progress|chapter] [--plot]

Arguments
---------
    --chapter       Chapter number to process, or ``all`` (default) to
                    iterate over [CHAPTER_START, CHAPTER_END] as set in
                    config.local.json. Inherited from Script.get_parser();
                    only the default is changed here.
    --sort          Row order of the table and the chart. ``progress``
                    (default): highest % concluded first, ties broken by
                    chapter number. ``chapter``: numeric chapter order.
    --plot          Also save a 100% stacked horizontal bar chart (one bar
                    per chapter) to STD_OUTPUT / status_report.png.
    -w / --write    Accepted (inherited) but ignored -- nothing is written
                    except the optional PNG.

Behaviour
---------
    Per chapter (processing()):
        1. Globs FIGURES_DIR / chapter<NN> / C*-*-*.md and loads the notes
           into a NoteCollFigure collection (same discovery as
           build_catalog.py).
        2. Classifies each note's ``status`` with classify_status() and
           stores one row of counts in self.rows. Chapters with 0 notes
           are skipped with a warning.

    After all chapters (run()):
        1. Builds a DataFrame from self.rows (get_report()), adds a TOTAL
           row and the percentage columns, and prints it.
        2. Only if --plot was passed: saves the chart (plot_report()).

Status classification
---------------------
    classify_status() mirrors the MVP rule of build_catalog.py
    (get_status_mvp / get_status_plain, kind="mvp"):

        contains "ftp"        -> concluded
        == "concluded"        -> concluded
        contains "pending"    -> pending
        == "stand-by"         -> standby
        anything else         -> undefined

    A missing status counts as "stand-by", as in build_catalog.py.

Key paths (resolved from config.local.json at import time)
-----------------------------------------------------------
    Notes root:  FIGURES_DIR / chapter<NN>/  (BASE_DIR / "figures/main")
    Chart out:   STD_OUTPUT / status_report.png  (--plot only)

Dependencies
------------
    losalamos.notes   NoteCollFigure
    catchy.core       Script, LOG_PREFIX, FIGURES_DIR, STD_OUTPUT, PBAR_FORMAT
    pandas            report table
    matplotlib        chart (imported only when --plot is passed)

Notes
-----
    - The classification rule is duplicated from build_catalog.py on
      purpose, to keep this report decoupled from the catalog pipeline
      (importing it would pull in DocumentTeX and the template paths). If
      the MVP rule changes there, update classify_status() too.
    - Percentages are of the chapter total, rounded to 1 decimal, so a row
      may not sum to exactly 100.
"""

# external
from tqdm import tqdm
import pandas as pd

from losalamos.notes import NoteCollFigure

# local
from catchy.core import *

STATUS_KEYS = ["concluded", "pending", "standby", "undefined"]

# status palette (dataviz reference: good / warning / serious / neutral)
STATUS_COLORS = {
    "concluded": "#0ca30c",
    "pending": "#fab219",
    "standby": "#ec835a",
    "undefined": "#a3a3a3",
}


def classify_status(status):
    """Maps a raw note status to one of STATUS_KEYS (MVP rule of
    build_catalog.py). None/NaN counts as "stand-by"."""
    if status is None or isinstance(status, float):
        s = "stand-by"
    else:
        s = str(status).replace('"', "").strip()

    if "ftp" in s:
        return "concluded"
    if s == "concluded":
        return "concluded"
    if "pending" in s:
        return "pending"
    if s == "stand-by":
        return "standby"
    return "undefined"


class ScriptReportStatus(Script):
    """
    Read-only figure status report, counted per chapter.

    :ivar rows: One dict of status counts per processed chapter.
    :vartype rows: list[dict]
    """

    TITLE = "REPORT STATUS"
    LOG_NAME = LOG_PREFIX.format("report-status")

    def __init__(self):
        super().__init__()
        self.rows = list()
        self.sort = "progress"
        self.plot = False

    def get_parser(self):
        """Adds --sort and --plot; defaults --chapter to 'all'."""
        parser = super().get_parser()
        parser.set_defaults(chapter="all")
        parser.add_argument(
            "--sort",
            choices=["progress", "chapter"],
            default="progress",
            help="Row order: 'progress' (highest %% concluded first) or "
                 "'chapter' (numeric).",
        )
        parser.add_argument(
            "--plot",
            action="store_true",
            default=False,
            help="Save a stacked bar chart to STD_OUTPUT/status_report.png.",
        )
        return parser

    def set_arguments(self, args):
        """Reads --sort and --plot on top of the inherited arguments."""
        super().set_arguments(args=args)
        self.sort = args.sort
        self.plot = args.plot

    def handle_mode(self, mode):
        """Skips the write gate: this script is read-only."""
        self.write = False
        self.print_info("Read-only report -- no note data is written")
        return 1

    def processing(self):
        """Loads the chapter notes and stores one row of status counts."""
        c_n = self.current_chapter
        chn = self.get_chapter_folder_name(c_n)
        ls_notes = list(FIGURES_DIR.glob(f"./{chn}/C*-*-*.md"))

        if len(ls_notes) == 0:
            self.print_warn("WARNING >>> 0 notes found")
            return None

        nc = NoteCollFigure()
        with tqdm(ls_notes, desc=" >>> ", unit="file", bar_format=PBAR_FORMAT) as pbar:
            nc.load_list(pbar)

        df = nc.catalog
        if "status" in df.columns:
            ls_status = df["status"].tolist()
        else:
            ls_status = [None] * len(df)

        dc_row = {"chapter": c_n, "total": len(ls_status)}
        for k in STATUS_KEYS:
            dc_row[k] = 0
        for s in ls_status:
            dc_row[classify_status(s)] += 1

        self.rows.append(dc_row)
        self.print_info(f"{chn} -- {len(ls_status)} notes counted")

    def get_report(self):
        """Returns the sorted report DataFrame (with TOTAL row and % columns),
        or None when no chapter had notes."""
        if len(self.rows) == 0:
            return None

        df = pd.DataFrame(self.rows)

        dc_total = {"chapter": "TOTAL", "total": df["total"].sum()}
        for k in STATUS_KEYS:
            dc_total[k] = df[k].sum()

        df = pd.concat([df, pd.DataFrame([dc_total])]).reset_index(drop=True)

        for k in STATUS_KEYS:
            df[f"%{k}"] = (100 * df[k] / df["total"]).round(1)

        # sort chapters only; TOTAL stays last
        df_ch = df[df["chapter"] != "TOTAL"].copy()
        df_tt = df[df["chapter"] == "TOTAL"].copy()
        if self.sort == "progress":
            df_ch = df_ch.sort_values(
                by=["%concluded", "chapter"], ascending=[False, True]
            )
        else:
            df_ch = df_ch.sort_values(by="chapter")

        df_ch["chapter"] = df_ch["chapter"].apply(lambda c: f"C{str(c).zfill(2)}")
        df = pd.concat([df_ch, df_tt]).reset_index(drop=True)

        return df

    def plot_report(self, df):
        """Saves a 100% stacked horizontal bar chart (one bar per chapter, in
        table order, top = first row) and returns the output path."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df_ch = df[df["chapter"] != "TOTAL"].iloc[::-1]
        total_row = df[df["chapter"] == "TOTAL"].iloc[0]

        fig_h = 1.2 + 0.35 * len(df_ch)
        fig, ax = plt.subplots(figsize=(8, fig_h))

        left = [0.0] * len(df_ch)
        for k in STATUS_KEYS:
            vals = df_ch[f"%{k}"].tolist()
            if sum(vals) == 0 and k == "undefined":
                continue
            ax.barh(
                df_ch["chapter"],
                vals,
                left=left,
                color=STATUS_COLORS[k],
                edgecolor="white",
                linewidth=1.5,
                height=0.7,
                label=k,
            )
            # direct labels (absolute counts) on segments wide enough to hold them
            counts = df_ch[k].tolist()
            for i, v in enumerate(vals):
                if v >= 6:
                    ax.text(
                        left[i] + v / 2, i, f"{counts[i]}",
                        ha="center", va="center", fontsize=8, color="#1a1a19",
                    )
            left = [a + b for a, b in zip(left, vals)]

        # chapter totals and stand-by count at the bar end
        ls_total = df_ch["total"].tolist()
        ls_standby = df_ch["standby"].tolist()
        for i, (n, p) in enumerate(zip(ls_total, ls_standby)):
            s = f"n={n}"
            if p > 0:
                s = s + f"  |  {p} stand-by"
            ax.text(101, i, s, va="center", fontsize=8, color="#555555")

        ax.set_xlim(0, 125)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xlabel("% of figures")
        ax.set_title(
            f"Figure status per chapter -- overall {total_row['%concluded']:.1f}% "
            f"concluded ({total_row['concluded']}/{total_row['total']})",
            fontsize=10, loc="left", pad=22,
        )
        for side in ["top", "right", "left"]:
            ax.spines[side].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.legend(
            ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0),
            frameon=False, fontsize=8,
        )

        fig.tight_layout()
        output = STD_OUTPUT / "status_report.png"
        fig.savefig(output, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return output

    def run(self):
        """Runs the chapter loop, then prints the report and saves the chart."""
        super().run()

        df = self.get_report()
        if df is None:
            self.print_warn("WARNING >>> no notes found in any chapter")
            return

        self.print_heading("=")
        print("STATUS REPORT\n")
        print(df.to_string(index=False))
        print("\n")

        if self.plot:
            fo = self.plot_report(df)
            self.print_info(f"chart saved: {fo}")


if __name__ == "__main__":

    s = ScriptReportStatus()
    s.run()
