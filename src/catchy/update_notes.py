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
