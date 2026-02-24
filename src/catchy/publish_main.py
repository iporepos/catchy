from pathlib import Path
import glob, pprint
import losalamos
from catchy.core import *

if __name__ == "__main__":
    Script.print_heading()
    print("PUBLISH MAIN FILES")

    # PROJECT PATH
    d = BASE_DIR.parent

    # LOAD PROJECT
    p = losalamos.load_project(project_folder=d)

    pattern = f"{d}/inputs/figures/main/chapter*"
    ls_dirs = glob.glob(pattern)

    output_folder = Path(p.folder_root) / "outputs/figures/main"
    Script.print_info(f"Output folder: {output_folder}")
    Script.print_info(f"Publishing {len(ls_dirs)} folders ...")

    p.publish_force = True

    o = p.publish(
        targets=ls_dirs,
        prefix=PREFIX_PUB_MAIN,
        output_folder=output_folder,
        surface=True
    )
    print("\n\n")
    pprint.pp(o)
    print("\n\n")
    Script.print_info("Done")