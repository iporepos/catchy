from losalamos.project import publish
from pathlib import Path
import shutil, os

PROJECT_PATH = Path(__file__).parent.parent.parent
CONFIG_FILE = PROJECT_PATH / "src/config.tex"
FIGURES_PATH = PROJECT_PATH / 'src/figures'
PUBLISH_PATH = PROJECT_PATH / 'src/published'
OVERLEAF_PATH = PROJECT_PATH / 'src/overleaf'
OVERLEAF_PATH2 = PROJECT_PATH / 'src/overleaf_zips'

import zipfile

def main():

    OVERLEAF_PATH.mkdir(parents=True, exist_ok=True)
    OVERLEAF_PATH2.mkdir(parents=True, exist_ok=True)

    for i in range(16):
        c = str(i).zfill(2)
        c_nm = f"chapter{c}"
        print(c_nm)
        f_tex = PUBLISH_PATH / f"{c_nm}_v202601.tex"
        if f_tex.exists():
            d = OVERLEAF_PATH / f"{c_nm}"
            d.mkdir(parents=True, exist_ok=True)

            d_figs = d / f"figures/{c_nm}"
            d_figs.mkdir(parents=True, exist_ok=True)

            f_tex_2 = d / f"{c_nm}.tex"
            shutil.copy(f_tex, f_tex_2)

            config_2 = d / "config.tex"
            shutil.copy(CONFIG_FILE, config_2)

            d_figs_src = FIGURES_PATH / f"{c_nm}"
            shutil.copytree(d_figs_src, d_figs, dirs_exist_ok=True)

            zip_path = OVERLEAF_PATH2 / f"{c_nm}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in d.rglob('*'):
                    if file.is_file():
                        zf.write(file, file.relative_to(d))
            print(f"  -> {zip_path}")

    # cleanup overleaf staging folder
    shutil.rmtree(OVERLEAF_PATH)
    print(f"Purged {OVERLEAF_PATH}")
    OVERLEAF_PATH.mkdir(parents=True, exist_ok=True)

if __name__ == '__main__':
    print(PROJECT_PATH)
    main()