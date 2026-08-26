import sys, subprocess
from pathlib import Path
import pandas as pd
from losalamos.notes import NoteFigure, NoteCollFigure

MAIN_FOLDER = Path(
    "C:/Users/Ipo/My Drive/athens/losalamos/B000/B005/inputs/figures/main"
)


def get_folder(c):
    return MAIN_FOLDER / f"chapter{c}"


def filder_df(df, collection):
    df_filter = df.query(f"collection == '{collection}'").copy()
    df_filter = df_filter.sort_values("order").reset_index(drop=True)
    return df_filter


def load_figures_notes(folder):
    nc = NoteCollFigure()
    nc.load_folder(folder=folder)
    df = nc.catalog[["note_name", "title", "collection", "order"]].copy()
    return df


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Retrieve references from figures")
    parser.add_argument("--chapter", "-c", type=int, help="chapter number")
    args = parser.parse_args()
    c = str(args.chapter).zfill(2)
    c_t12 = f"chapter{c}_T12.tex"
    src = Path(c_t12)

    if not src.exists():
        print(f"Error: file not found: {src}")
        sys.exit(1)

    notes_folder = get_folder(c)
    print(notes_folder)
    df = load_figures_notes(notes_folder)
    df["title"] = [s.replace('"', "") for s in df["title"]]
    df["number"] = [s.split(" ")[1] for s in df["title"]]

    df_cover = filder_df(df, "cover")
    df_figures = filder_df(df, "main text")
    df_boxes = filder_df(df, "box")
    df_bios = filder_df(df, "biography")

    # print(df_boxes)
    # print(df_bios)

    # Cover
    # =====================================================
    df_cover_placeholder = df_cover.copy()
    df_cover_reference = df_cover.copy()
    df_cover_placeholder["old"] = [
        "openingimage{Figure " + number + "}{"
        for number in df_cover_placeholder["number"]
    ]
    df_cover_placeholder["new"] = [
        "openingimage{" + number + "}{"
        for number in df_cover_placeholder["note_name"]
    ]
    #print(df_cover_placeholder[["old", "new"]].to_string())

    df_cover_reference["old"] = [
        r"Figure~\ref{fig:" + number + "}"
        for number in df_cover_reference["number"]
    ]
    df_cover_reference["new"] = [
        r"\Cref{" + number + "}"
        for number in df_cover_reference["note_name"]
    ]
    #print(df_figures_reference[["old", "new"]].to_string())

    df_cover_replacers = pd.concat([df_cover_placeholder, df_cover_reference]).reset_index(drop=True)
    #print(df_cover_replacers.to_string())

    # Figures
    # =====================================================
    df_figures_placeholder = df_figures.copy()
    df_figures_reference = df_figures.copy()
    df_figures_reference_abrev = df_figures.copy()
    df_figures_reference_simple = df_figures.copy()
    df_figures_reference_simple_abrev = df_figures.copy()
    df_figures_reference_a = df_figures.copy()
    df_figures_reference_b = df_figures.copy()
    df_figures_reference_c = df_figures.copy()

    df_figures_placeholder["old"] = [
        "figplaceholder{fig:" + number + "}{Figure " + number + "}{"
        for number in df_figures_placeholder["number"]
    ]
    df_figures_placeholder["new"] = [
        "figplaceholder{" + number + "}{" + number + "}{"
        for number in df_figures_placeholder["note_name"]
    ]
    #print(df_figures_placeholder[["old", "new"]].to_string())

    df_figures_reference["old"] = [
        r"Figure~\ref{fig:" + number + "}"
        for number in df_figures_reference["number"]
    ]
    df_figures_reference["new"] = [
        r"\Cref{" + number + "}"
        for number in df_figures_reference["note_name"]
    ]

    df_figures_reference_abrev["old"] = [
        r"Fig.~\ref{fig:" + number + "}"
        for number in df_figures_reference_abrev["number"]
    ]
    df_figures_reference_abrev["new"] = [
        r"\Cref{" + number + "}"
        for number in df_figures_reference_abrev["note_name"]
    ]

    df_figures_reference_simple["old"] = [
        "Figure~" + number
        for number in df_figures_reference_simple["number"]
    ]
    df_figures_reference_simple["new"] = [
        r"\Cref{" + number + "}"
        for number in df_figures_reference_simple["note_name"]
    ]

    df_figures_reference_simple_abrev["old"] = [
        "Fig.~" + number
        for number in df_figures_reference_simple_abrev["number"]
    ]
    df_figures_reference_simple_abrev["new"] = [
        r"\Cref{" + number + "}"
        for number in df_figures_reference_simple_abrev["note_name"]
    ]

    df_figures_reference_a["old"] = [
        r"Figure~\ref{fig:" + number + "a}"
        for number in df_figures_reference_a["number"]
    ]
    df_figures_reference_a["new"] = [
        r"\Cref{" + number + "}"
        for number in df_figures_reference_a["note_name"]
    ]

    df_figures_reference_b["old"] = [
        r"Figure~\ref{fig:" + number + "b}"
        for number in df_figures_reference_b["number"]
    ]
    df_figures_reference_b["new"] = [
        r"\Cref{" + number + "}"
        for number in df_figures_reference_b["note_name"]
    ]

    df_figures_reference_c["old"] = [
        r"Figure~\ref{fig:" + number + "c}"
        for number in df_figures_reference_c["number"]
    ]
    df_figures_reference_c["new"] = [
        r"\Cref{" + number + "}"
        for number in df_figures_reference_c["note_name"]
    ]

    #print(df_figures_reference[["old", "new"]].to_string())

    df_figures_replacers = pd.concat([
        df_figures_placeholder,
        df_figures_reference,
        df_figures_reference_abrev,
        df_figures_reference_simple,
        df_figures_reference_simple_abrev,
        df_figures_reference_a,
        df_figures_reference_b,
        df_figures_reference_c
    ]).reset_index(drop=True)
    #print(df_figures_replacers.to_string())

    # Boxes
    # ==========================================
    df_box_reference = df_boxes.copy()
    df_box_placeholder = df_boxes.copy()
    df_box_label = df_boxes.copy()

    df_box_placeholder["old"] = [
        r"boxfigplaceholder{Box " + number + "}"
        for number in df_box_placeholder["number"]
    ]
    df_box_placeholder["new"] = [
        r"boxfigplaceholder{" + number + "}"
        for number in df_box_placeholder["note_name"]
    ]

    df_box_label["old"] = [
        r"}[label=Box " + number + "]{"
        for number in df_box_label["number"]
    ]
    df_box_label["new"] = [
        r"}[label=" + number + "]{"
        for number in df_box_label["note_name"]
    ]

    df_box_reference["old"] = [
        r"Box~" + number
        for number in df_box_reference["number"]
    ]
    df_box_reference["new"] = [
        r"\Cref{" + number + "}"
        for number in df_box_reference["note_name"]
    ]

    df_box_replacers = pd.concat([df_box_reference, df_box_label, df_box_placeholder]).reset_index(drop=True)
    #print(df_box_replacers.to_string())

    # Bios
    # ======================

    df_bio_placeholder = df_bios.copy()
    df_bio_placeholder["old"] = [
        r"\boxbiofigplaceholder{Biography " + number + "}"
        for number in df_bio_placeholder["number"]
    ]
    df_bio_placeholder["new"] = [
        r"\boxbiofigplaceholder{" + number + "}"
        for number in df_bio_placeholder["note_name"]
    ]
    df_bio_replacers = df_bio_placeholder.copy()
    #print(df_bio_replacers.to_string())

    df_output = pd.concat([df_cover_replacers, df_figures_replacers, df_box_replacers, df_bio_replacers]).reset_index(drop=True)

    df_output = df_output[["old", "new"]].copy()
    print(df_output.to_string())

    fo = src.parent / f"{src.stem}_references.csv"
    df_output.to_csv(fo, sep=",", index=False)


if __name__ == "__main__":
    main()
