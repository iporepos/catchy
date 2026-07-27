#!/usr/bin/env python3
r"""
make_catalog.py

Generates a comprehensive single-document specimen sheet of Latin and
Greek letters and basic math operators, for manual PDF -> SVG export.

Font setup: Latin letters use FONT (your Wiley-specified text font).
Greek letters and math operators use GREEK_FONT / MATH_FONT instead --
Times-family fonts (including Times LT Std) generally don't contain
Greek or operator glyphs at all; STIX was designed specifically to
fill that gap while staying visually compatible with Times, which is
also why Wiley's own book-font policy recommends STIX for math
material specifically, separate from the Helvetica/Times used for
regular text.

The font size is NOT hand-picked -- it's computed by LaTeX itself at
compile time, by rendering a capital "H" at a large reference size,
measuring its actual cap height, and solving for the size that makes
the cap height exactly TARGET_CAP_HEIGHT_MM. This makes the sheet
self-calibrating: swap the font and it recalibrates automatically,
no guessing at point sizes from assumed font metrics.

Convention used (standard math-typesetting practice):
    - Latin letters (upper + lower): italic
    - Greek lowercase: italic
    - Greek uppercase: upright (they're used as distinct symbols,
      e.g. Delta, Omega, Sigma -- not "slanted Latin")

Compound symbols (fraction, sum/integral with limits) briefly enter
math mode ONLY to borrow LaTeX's fraction-bar and limit-stacking
geometry (\dfrac, \mathop...\limits) -- every actual glyph inside is
wrapped in \text{} so it still renders in our chosen font rather than
LaTeX's default Computer Modern math font. This is the same
font-substitution trap that caused the original PDF/SVG mismatch
early on, so it's deliberately avoided here too.

Requires: xelatex (for real system fonts via fontspec). GREEK_FONT and
MATH_FONT must be installed too -- STIX is free (SIL Open Font
License): https://github.com/stipub/stixfonts/releases
"""

from pathlib import Path

FONT = "Times LT Std"           # Latin letters -- your Wiley-specified font
GREEK_FONT = "STIX Two Math"    # Greek letters -- confirmed you have this installed
MATH_FONT = "STIX Two Math"     # operators -- same font covers both
TARGET_CAP_HEIGHT_MM = 1.8      # height of uppercase Latin letters
COLUMNS = 13                    # grid columns per row (26 Latin -> 2 clean rows)

LATIN_UPPER = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
LATIN_LOWER = [chr(c) for c in range(ord("a"), ord("z") + 1)]

GREEK_UPPER_NAMES = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta",
                      "Eta", "Theta", "Iota", "Kappa", "Lambda", "Mu", "Nu",
                      "Xi", "Omicron", "Pi", "Rho", "Sigma", "Tau",
                      "Upsilon", "Phi", "Chi", "Psi", "Omega"]
GREEK_UPPER_CODES = [0x391, 0x392, 0x393, 0x394, 0x395, 0x396, 0x397, 0x398,
                      0x399, 0x39A, 0x39B, 0x39C, 0x39D, 0x39E, 0x39F, 0x3A0,
                      0x3A1, 0x3A3, 0x3A4, 0x3A5, 0x3A6, 0x3A7, 0x3A8, 0x3A9]

GREEK_LOWER_NAMES = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta",
                      "eta", "theta", "iota", "kappa", "lambda", "mu", "nu",
                      "xi", "omicron", "pi", "rho", "sigma_final", "sigma",
                      "tau", "upsilon", "phi", "chi", "psi", "omega"]
GREEK_LOWER_CODES = [0x3B1, 0x3B2, 0x3B3, 0x3B4, 0x3B5, 0x3B6, 0x3B7, 0x3B8,
                      0x3B9, 0x3BA, 0x3BB, 0x3BC, 0x3BD, 0x3BE, 0x3BF, 0x3C0,
                      0x3C1, 0x3C2, 0x3C3, 0x3C4, 0x3C5, 0x3C6, 0x3C7, 0x3C8,
                      0x3C9]

# Basic operators: arithmetic, summation, integral family, partial
# derivative, nabla, and the upright "d" used in dx/dt notation
# (deliberately upright, not italic -- that's the standard convention
# distinguishing the differential operator from an italic variable
# named d, which is already in the Latin lowercase set above).
# Rendered in MATH_FONT (see top of file), not FONT.
MATH_OP_NAMES = ["plus", "minus", "times", "division",
                  "sum", "integral", "double_integral", "triple_integral",
                  "contour_integral", "partial", "nabla", "d_operator"]
MATH_OP_CODES = [0x002B, 0x2212, 0x00D7, 0x00F7,
                  0x2211, 0x222B, 0x222C, 0x222D, 0x222E, 0x2202, 0x2207,
                  ord("d")]


def char_symbol(glyph: str, italic: bool) -> str:
    """A single Unicode character, optionally italicised."""
    return rf"\textit{{{glyph}}}" if italic else glyph


def fraction_symbol(num: str = "a", den: str = "b") -> str:
    """Generic a-over-b fraction template. Uses \\dfrac purely for its
    fraction-bar/spacing geometry; \\text{} keeps the glyphs in our font
    rather than Computer Modern math italic."""
    return (rf"$\dfrac{{\text{{\textit{{{num}}}}}}}"
            rf"{{\text{{\textit{{{den}}}}}}}$")


def limits_symbol(op_char: str, lower: str, upper: str) -> str:
    """An operator (sum/integral/...) with example lower/upper limits,
    e.g. sum_{i=1}^{n}. \\mathop{}\\limits provides the stacking
    geometry; \\text{} again keeps everything in our font."""
    return (rf"$\mathop{{\text{{{op_char}}}}}\limits"
            rf"_{{\text{{\scriptsize\textit{{{lower}}}}}}}"
            rf"^{{\text{{\scriptsize\textit{{{upper}}}}}}}$")


COMPOUND_NAMES = ["fraction", "sum_limits", "integral_limits"]
COMPOUND_SYMBOLS = [
    fraction_symbol("a", "b"),
    limits_symbol(chr(0x2211), "i=1", "n"),
    limits_symbol(chr(0x222B), "a", "b"),
]


def cell(label: str, symbol_latex: str) -> str:
    safe_label = label.replace("_", r"\_")
    return rf"\shortstack{{\Sym{{{symbol_latex}}}\\[2pt]\tiny\texttt{{{safe_label}}}}}"


def grid(labels: list[str], symbols: list[str], columns: int) -> str:
    cells = [cell(lbl, sym) for lbl, sym in zip(labels, symbols)]
    rows = [cells[i:i + columns] for i in range(0, len(cells), columns)]
    colspec = "*{%d}{c}" % columns
    body = " \\\\[3mm]\n".join(" & ".join(row) for row in rows)
    return f"\\begin{{tabular}}{{{colspec}}}\n{body}\n\\end{{tabular}}"


def section(title: str, latex_grid: str) -> str:
    return f"\\subsection*{{{title}}}\n{latex_grid}\n\\vspace{{4mm}}\n"


def build_tex() -> str:
    latin_upper = grid(LATIN_UPPER,
                        [char_symbol(g, italic=True) for g in LATIN_UPPER],
                        columns=COLUMNS)
    latin_lower = grid(LATIN_LOWER,
                        [char_symbol(g, italic=True) for g in LATIN_LOWER],
                        columns=COLUMNS)
    greek_upper = grid(GREEK_UPPER_NAMES,
                        [char_symbol(chr(c), italic=False) for c in GREEK_UPPER_CODES],
                        columns=COLUMNS)
    greek_lower = grid(GREEK_LOWER_NAMES,
                        [char_symbol(chr(c), italic=True) for c in GREEK_LOWER_CODES],
                        columns=COLUMNS)
    math_ops = grid(MATH_OP_NAMES,
                     [char_symbol(chr(c), italic=False) for c in MATH_OP_CODES],
                     columns=COLUMNS)
    compound = grid(COMPOUND_NAMES, COMPOUND_SYMBOLS, columns=COLUMNS)

    body = "\n".join([
        section("Latin --- Uppercase", latin_upper),
        section("Latin --- Lowercase", latin_lower),
        section("Greek --- Uppercase", "{\\GreekFont " + greek_upper + "}"),
        section("Greek --- Lowercase", "{\\GreekFont " + greek_lower + "}"),
        section("Math Operators", "{\\MathOpFont " + math_ops + "}"),
        section("Compound Operators", "{\\MathOpFont " + compound + "}"),
    ])

    return rf"""\documentclass[10pt]{{article}}
\usepackage{{fontspec}}
\usepackage{{amsmath}}
\setmainfont{{{FONT}}}
\newfontfamily\GreekFont{{{GREEK_FONT}}}
\newfontfamily\MathOpFont{{{MATH_FONT}}}
\usepackage[a4paper, margin=15mm]{{geometry}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}

\newdimen\refCapHt
\newdimen\refSize
\newdimen\targetCapHt
\newdimen\symFontSize

\begin{{document}}
% --- Self-calibrate: find the font size that makes cap-height of
%     uppercase Latin letters exactly {TARGET_CAP_HEIGHT_MM}mm ---
\refSize=100pt
\targetCapHt={TARGET_CAP_HEIGHT_MM}mm
\begingroup
  \fontsize{{\refSize}}{{1.2\refSize}}\selectfont
  \setbox0=\hbox{{\textit{{H}}}}
  \global\refCapHt=\ht0
\endgroup
\symFontSize=\dimexpr \targetCapHt*\refSize/\refCapHt\relax
\newcommand{{\Sym}}[1]{{\fontsize{{\symFontSize}}{{1.2\symFontSize}}\selectfont #1}}

\begin{{center}}
{{\small\itshape Cap height calibrated to {TARGET_CAP_HEIGHT_MM}\,mm at computed size \the\symFontSize{{}}\\
Latin: \texttt{{{FONT}}} \quad Greek: \texttt{{{GREEK_FONT}}} \quad Operators: \texttt{{{MATH_FONT}}}}}
\end{{center}}
\vspace{{4mm}}

{body}
\end{{document}}
"""


def main():
    tex = build_tex()
    out = Path("./outputs/catalog.tex")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tex, encoding="utf-8")
    print(f"Wrote {out} -- compile with:  xelatex {out.name}")


if __name__ == "__main__":
    main()