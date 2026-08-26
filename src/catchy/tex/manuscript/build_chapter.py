import sys, shutil
from datetime import datetime
from pathlib import Path
from losalamos.documents import DocumentTeX


def backup_file(src):
    bkp_folder = src.parent / "backup"
    bkp_folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = bkp_folder / src.with_name(src.stem + "_" + ts + src.suffix)
    shutil.copy(src, backup)
    print("[BACKUP] Backup saved to {}".format(backup))


def build_chapter(src):
    doc = DocumentTeX()
    doc.load_data(file_data=src)
    doc.to_pdf(cleanup=True)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Build Chapter PDF",
    )
    parser.add_argument("--chapter", "-c", type=int, help="chapter number")
    parser.add_argument("--backup", "-b", action="store_true", help="chapter number")
    parser.add_argument("--tier", "-t", type=str, default="12", help="chapter tier")
    args = parser.parse_args()
    c = str(args.chapter).zfill(2)
    c_t12 = f"chapter{c}_T{args.tier}.tex"
    src = Path(c_t12)

    if not src.exists():
        print(f"Error: file not found: {src}")
        sys.exit(1)

    build_chapter(src)

    if args.backup:
        backup_file(src)


if __name__ == "__main__":
    main()
