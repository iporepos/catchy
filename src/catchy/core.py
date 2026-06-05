"""
Core Module
===========

This module establishes the foundational configuration, directory paths, and
base scripting functionalities for the project.

It dynamically loads local configurations from ``config.local.json`` to set up
essential path constants (e.g., base directories, figures, documents, data).
Additionally, it provides the base :class:`Script` class to handle common
Command-Line Interface (CLI) operations, user confirmation gates, standard
logging, and chapter-wise execution flows.
"""
# IMPORTS
# ***********************************************************************
# import modules from other libs

# Native imports
# =======================================================================
import argparse
import glob
import os
import re
import pprint
import shutil
import json
from pathlib import Path
from time import sleep

# ... {develop}

# External imports
# =======================================================================
# ... {develop}

# CONSTANTS
# ***********************************************************************
# define constants in uppercase

HERE = Path(__file__).parent.parent.parent.absolute()
CONFIG = HERE / "config.local.json"
with open(CONFIG) as f:
    config = json.load(f)

BASE_DIR = Path(config["base_dir"])
STD_OUTPUT = Path(config["std_output"])
CHAPTER_START = int(config["chapter_start"])
CHAPTER_END = int(config["chapter_end"])

FIGURES_DIR = BASE_DIR / "figures/main"
CAPTIONS_DIR = FIGURES_DIR / "captions"
DOCUMENTS_DIR = BASE_DIR / "documents"
CATALOG_DIR = BASE_DIR / "Catalogue"
DATA_DIR = BASE_DIR / "data"

PREFIX_PUB_MAIN = str(config["prefix_publish_main"])
PREFIX_PUB_SRC = str(config["prefix_publish_src"])

NOTE_PATTERN = "C*-*-*.md"
LOG_PREFIX = "cathy @ {}:"

FIGS_PREFIXES = {
    "cover": "Figure",
    "main text": "Figure",
    "box": "Box",
    "biography": "Biography",
}

# FUNCTIONS
# ***********************************************************************


class Script:
    """
    Base class for executing chapter-processing scripts.

    This class provides a standardized framework for command-line argument parsing,
    execution mode management (enforcing safe mode versus write mode with user
    confirmation), standard console output/logging, and batch chapter iteration.
    It is designed to be subclassed, where specific logic should be implemented
    by overriding the :meth:`processing` method.

    :cvar TITLE: The title of the script, displayed upon execution.
    :type TITLE: str
    :cvar LOG_NAME: The standard prefix used for console logging outputs.
    :type LOG_NAME: str

    :ivar write: Flag indicating whether the script is permitted to overwrite data.
    :vartype write: bool
    :ivar src_dir: The source directory path for the current chapter being processed.
    :vartype src_dir: pathlib.Path or None
    :ivar current_chapter: The specific chapter number currently being processed.
    :vartype current_chapter: int or None
    """
    TITLE = "BASE SCRIPT"
    LOG_NAME = LOG_PREFIX.format("script")

    def __init__(self):
        self.write = False
        self.src_dir = None
        self.current_chapter = None

    def get_parser(self):
        # 1. Initialize the Parser
        parser = argparse.ArgumentParser(
            description="Parse arguments",
            epilog="Usage example: python script.py data.csv --limit 10 -v",
        )

        # 2. Add Arguments

        # Positional argument (Required)
        parser.add_argument("--chapter", help="Number of chapter")

        # Flag/Boolean argument (True if present, False otherwise)
        parser.add_argument(
            "-w",
            "--write",
            action="store_true",
            help="Set as writing mode",
        )

        return parser

    def get_arguments(self):

        parser = self.get_parser()

        # 3. Parse the Arguments
        args = parser.parse_args()

        return args

    def set_arguments(self, args):
        self.write = args.write

    @classmethod
    def print_info(cls, msg):
        print(f" >>> {cls.LOG_NAME} INFO {msg}")

    @classmethod
    def print_step(cls, msg):
        print(f" >>> {cls.LOG_NAME} STEP {msg}")

    @classmethod
    def print_warn(cls, msg):
        print(f" >>> {cls.LOG_NAME} WARN {msg}")

    @staticmethod
    def print_chap(c_n):
        c = str(c_n).zfill(2)
        Script.print_heading()
        print(f"Processing: Chapter {c}\n")

    @staticmethod
    def print_heading(char="="):
        print("\n\n")
        print(80 * char)

    @staticmethod
    def get_chapter_folder_name(c_n):
        c = str(c_n).zfill(2)
        return f"chapter{c}"

    @staticmethod
    def handle_chapter(c_n):
        if c_n == "all":
            chapters = [i for i in range(CHAPTER_START, CHAPTER_END + 1)]
            return chapters
        else:
            chapters = [int(c_n)]
            return chapters

    def gate_keeper(self, msg):
        self.print_warn("WARNING")
        self.print_info(msg)
        ans = input("confirm execution? [y/N] ")
        return ans in ("y", "yes")

    def handle_mode(self, mode):
        print("\n\n")
        print(80 * "=")
        print("WRITING MODE")
        if mode:
            if self.gate_keeper("This script will overwrite data\n"):
                self.print_step("Writing confirmed (write mode)")
                self.write = True
                return 0
            else:
                self.print_warn("Writing cancelled (entering safe mode)")
                self.write = False
                return 1
        else:
            self.write = False
            self.print_warn("Execution in safe mode -- NO WRITING")
            ans = input("press any key to continue: ")
            return 1

    def run(self):

        self.print_heading("=")
        print(self.TITLE)

        args = self.get_arguments()
        self.set_arguments(args=args)

        # Write gate
        # ------------------------------------------------------------------
        ans = self.handle_mode(self.write)

        # handle chapter
        # ------------------------------------------------------------------
        c_n = args.chapter
        chapters = self.handle_chapter(c_n)

        for chapter in chapters:

            self.print_chap(chapter)
            self.current_chapter = chapter

            self.print_step("Starting processing")
            self.processing()

        self.print_step("Done")

    def set_src_dir(self, c_n):
        cnm = self.get_chapter_folder_name(c_n)
        self.src_dir = FIGURES_DIR / cnm

    def processing(self):
        print("okok")


if __name__ == "__main__":

    print(BASE_DIR)
    print(CAPTIONS_DIR)
    print(DATA_DIR)

    print("Hello World!")

    s = Script()
    s.run()
