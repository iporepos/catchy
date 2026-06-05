"""
ScriptUpdateNotes — Batch Metadata Updater for Figure Notes
===========================================================
Iterates over all figure note files in a chapter directory and synchronises
their YAML front-matter fields (tags, title, aliases, abstract, file links)
to the values derived from the note's own metadata and project conventions.

Subclasses :class:`losalamos.tools.core.Script`, inheriting CLI argument
parsing (``--chapter``, ``--write``), safe/write mode gating with user
confirmation, standard console logging (INFO / STEP / WARN), and chapter
iteration over the range defined in ``config.local.json``.

Usage
-----
    python update_notes.py --chapter <N|all> [-w]

Arguments
---------
    --chapter       Chapter number to process, or ``all`` to iterate over
                    [CHAPTER_START, CHAPTER_END] as set in config.local.json.
                    Inherited from Script.get_parser().
    -w / --write    Enable write mode. Without this flag, notes are loaded
                    and processed but n.save() is never called (safe mode
                    sleeps 10 ms per note to simulate work). With it, a
                    confirmation prompt is shown before any files are touched.

Behaviour (per chapter)
-----------------------
    1. Resolves src_dir via Script.set_src_dir() →
       FIGURES_DIR / chapter<NN>.
    2. Globs for note files matching NOTE_PATTERN (C*-*-*.md).
    3. For each note, loads YAML front-matter via NoteFigure.load() and
       updates the following fields:

       tags        ← fixed list: figure, losalamos, hydrology, science,
                      illustration
       title       ← "<Prefix> <chapter>.<order>"  where Prefix comes from
                      FIGS_PREFIXES[collection] (Figure / Box / Biography)
       aliases     ← [title]  (single-element list mirroring title)
       abstract    ← copied from caption; written to note heading via
                      n.update_abstract(), then reset to None in metadata
       file        ← "[[<name>_T1.jpeg]]" (png for collection == 'box')
       file_draft  ← "[[<name>_T0.jpeg]]"

    4. Saves via n.save() only when write mode is active.

Key paths (resolved from config.local.json at import time)
-----------------------------------------------------------
    Notes root:   FIGURES_DIR / chapter<NN>/  (BASE_DIR / "figures/main")
    Note pattern: NOTE_PATTERN = "C*-*-*.md"

Dependencies
------------
    losalamos.notes       NoteFigure
    losalamos.tools.core  Script, LOG_PREFIX, NOTE_PATTERN,
                          FIGURES_DIR, FIGS_PREFIXES
    catchy.core           (project-level utilities)

Notes
-----
    - The abstract field is intentionally reset to None in metadata after
      n.update_abstract() writes it to the note body; this prevents the
      field from being double-stored in both the heading and the front-matter.
    - File suffix logic: all collections use .jpeg except 'box', which
      uses .png — reflects the downstream rendering format per collection type.
    - Re-running is safe: every field is deterministically derived from
      existing metadata, so repeated runs produce identical output.
    - If 0 notes are found the script warns and exits the chapter cleanly
      without raising an exception.
"""
import time
from tqdm import tqdm
from losalamos.notes import NoteFigure
from catchy.core import *


class ScriptUpdateNotes(Script):
    TITLE = "UPDATE NOTES"
    LOG_NAME = LOG_PREFIX.format("update-notes")

    TAGS = [
        "figure",
        "losalamos",
        "hydrology",
        "science",
        "illustration",
    ]

    def processing(self):
        c_n = self.current_chapter
        self.set_src_dir(c_n=self.current_chapter)

        # Retrieve files
        # ------------------------------------------------------------------
        pattern = f"{self.src_dir}/{NOTE_PATTERN}"
        ls_notes = glob.glob(pattern)

        if len(ls_notes) == 0:
            self.print_warn("WARNING >>> 0 notes found")
            return None

        # Enter file loop
        # ------------------------------------------------------------------
        self.print_step(f"updating notes ... ")

        for f_note in tqdm(ls_notes, desc="Updating notes", unit="note"):
            p = Path(f_note)

            # self.print_step(f"updating {p.name}")

            # Load
            # ---------------------------------------
            n = NoteFigure()
            n.file_note = p
            n.load()

            # set tags
            # ---------------------------------------
            n.metadata["tags"] = self.TAGS

            # set title
            # ---------------------------------------
            collection = n.metadata["collection"]
            order = int(n.metadata["order"])
            title = f'"{FIGS_PREFIXES[collection]} {c_n}.{order}"'
            n.metadata["title"] = title

            # set Alias
            # ---------------------------------------
            n.metadata["aliases"] = [n.metadata["title"]]

            # set Abstract in the note heading
            # ---------------------------------------
            n.metadata["abstract"] = n.metadata["caption"]
            n.update_abstract()  # data update
            n.metadata["abstract"] = None  # reset to None

            # set files
            # ---------------------------------------
            label = n.metadata["name"].strip('"')
            suf = "jpeg"
            if collection == "box":
                suf = "png"

            n.metadata["file"] = '"[[{}_T1.{}]]"'.format(label, suf)
            n.metadata["file_draft"] = '"[[{}_T0.jpeg]]"'.format(label)


            # Save
            # ---------------------------------------
            if self.write:
                n.save()
            else:
                time.sleep(0.01)

        self.print_step("Done")
        return None


if __name__ == "__main__":

    s = ScriptUpdateNotes()
    s.run()
