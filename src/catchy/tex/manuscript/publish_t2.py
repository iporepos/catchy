import glob, shutil, os
from pathlib import Path



def main():
    ls_files1 = glob.glob("chapter*_T2.tex")
    ls_files2 = glob.glob("chapter*_T2.pdf")
    ls_files = ls_files1 + ls_files2

    print(ls_files)

    for f in ls_files:
        p = Path(f)
        nm = p.stem
        ext = p.suffix
        nm2 = nm.split("_")[0] + "_v202601" + ext
        print(nm2)
        p2 = p.parent / f"published/{nm2}"
        shutil.copy(str(p), str(p2))

if __name__ == '__main__':
    main()