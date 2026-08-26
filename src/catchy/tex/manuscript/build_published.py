import sys, shutil
from datetime import datetime
from pathlib import Path
from losalamos.documents import DocumentTeX

FOLDER = Path(__file__).parent.parent / "published"

def build_chapter(src):
    doc = DocumentTeX()
    doc.load_data(file_data=src)
    doc.to_pdf(cleanup=True)


def main():

    ls = [i for i in range(0, 16)]
    ls = [11]

    for i in ls:
        c = str(i).zfill(2)
        c_nm = f"chapter{c}_v202601.tex"

        src = FOLDER / c_nm

        if not src.exists():
            print(f"Error: file not found: {src}")
            continue

        build_chapter(src)



if __name__ == "__main__":
    main()
