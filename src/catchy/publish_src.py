"""
publish_src — Publish Source Figure Files
=========================================
Batch-publishes all chapter source-figure folders from the project's input
tree to the designated output directory, using the losalamos publish pipeline.

Mirrors publish_main.py in structure and behaviour, but targets the ``src``
figure tree (raw/editable source files) rather than the ``main`` (processed)
tree, and uses PREFIX_PUB_SRC instead of PREFIX_PUB_MAIN.

Usage
-----
    python publish_src.py

Behaviour
---------
    1. Resolves the project root as BASE_DIR.parent and loads the project
       via losalamos.load_project().
    2. Globs all chapter subdirectories matching:
           <project_root>/inputs/figures/src/chapter*
    3. Sets output destination to:
           <project_root>/outputs/figures/src/
    4. Calls p.publish() with publish_force=True (overwrites existing files)
       and surface=True over all discovered chapter folders.
    5. Pretty-prints the publish result object and exits.

Key paths (resolved from config.local.json at import time)
-----------------------------------------------------------
    Input glob:    BASE_DIR.parent / inputs/figures/src/chapter*
    Output root:   BASE_DIR.parent / outputs/figures/src/
    Pub prefix:    PREFIX_PUB_SRC  (set in config.local.json)

Dependencies
------------
    losalamos          load_project(), project.publish()
    catchy.core        BASE_DIR, PREFIX_PUB_SRC, Script (for print helpers)

See Also
--------
    publish_main.py — identical pipeline over the ``main`` figure tree.

Notes
-----
    - publish_force=True means existing output files are overwritten without
      prompting. There is no dry-run mode; verify the output folder before
      running in sensitive environments.
    - surface=True instructs the publisher to surface files to the top-level
      output folder rather than preserving the full input subdirectory tree.
    - The result object ``o`` returned by p.publish() is printed raw via
      pprint.pp() — inspect it to confirm which files were written or skipped.
    - If ls_dirs is empty (no chapter* folders found), publish() will be
      called with an empty target list; behaviour in that case depends on
      losalamos internals.
"""
import losalamos
from catchy.core import *

if __name__ == "__main__":
    Script.print_heading()
    print("PUBLISH SRC FILES")

    # PROJECT PATH
    d = BASE_DIR.parent

    # LOAD PROJECT
    p = losalamos.load_project(project_folder=d)

    pattern = f"{d}/inputs/figures/src/chapter*"
    ls_dirs = glob.glob(pattern)

    output_folder = Path(p.folder_root) / "outputs/figures/src"
    Script.print_info(f"Output folder: {output_folder}")
    Script.print_info(f"Publishing {len(ls_dirs)} folders ...")

    p.publish_force = True

    o = p.publish(
        targets=ls_dirs,
        prefix=PREFIX_PUB_SRC,
        output_folder=output_folder,
        surface=True,
    )

    print("\n\n")
    pprint.pp(o)
    print("\n\n")
    Script.print_info("Done")
