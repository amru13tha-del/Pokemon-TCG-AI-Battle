"""Builds architecture.png -- the M1 agent system-flow diagram for the
Strategy Writeup media gallery.

Every box corresponds to real shipped code:
  main.agent / _policy / _legal_fallback   -> main.py
  hard_override + Rules 1-3                -> src/baseline.py::hard_override
  baseline_score scalar table              -> src/baseline.py::baseline_score
  weakness x2 / resistance -30 / floor dmg -> src/baseline.py::_guaranteed_damage

Layout note: box heights are COMPUTED from line count, never hand-guessed --
an earlier hand-guessed version overlapped badly. ASCII only (box-drawing
glyphs are missing from the bundled fonts and render as tofu).
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

SURFACE = "#FFFFFF"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
CRITICAL = "#d03b3b"
GREY = "#a8a69f"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
})

DPI = 200
FIG_W = 1600 / DPI
FIG_H = 7.8

LINESPACING = 1.5
PAD_V = 0.017     # vertical padding inside a box (top and bottom each)
BOXSTYLE_PAD = 0.004  # FancyBboxPatch draws this far beyond the nominal rect
MIN_GAP = 0.013   # >= 2 * BOXSTYLE_PAD, so adjacent boxes never touch

SPINE_X = 0.045
SPINE_W = 0.545
SIDE_X = 0.625
SIDE_W = 0.335


def line_h(fontsize):
    """Exact axes-fraction height of one rendered text line. Points are
    absolute, the axes is a fraction of FIG_H -- so this has to be derived,
    not guessed (a guessed constant is what made the first version overlap)."""
    return (fontsize * LINESPACING / 72.0) / FIG_H


def box(ax, x, y_top, w, lines, facecolor, edgecolor, fontsize=8.2,
        weight="normal", align="center", textcolor=INK, title=None):
    """Draws a box whose height is computed from real font metrics.
    Returns the y-coordinate of its bottom edge."""
    n = len(lines)
    h = n * line_h(fontsize) + 2 * PAD_V
    y = y_top - h
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.010",
        facecolor=facecolor, edgecolor=edgecolor, linewidth=1.5, zorder=3))
    text = "\n".join(lines)
    if align == "center":
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, color=textcolor, zorder=4,
                fontweight=weight, linespacing=LINESPACING)
    else:
        ax.text(x + 0.016, y + h / 2, text, ha="left", va="center",
                fontsize=fontsize, color=textcolor, zorder=4,
                fontweight=weight, linespacing=LINESPACING)
    return y


def arrow(ax, x1, y1, x2, y2, color=INK2, lw=1.5, ls="-", style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                 mutation_scale=12, color=color, lw=lw,
                                 linestyle=ls, zorder=2, shrinkA=0, shrinkB=0))


def build():
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(SURFACE)

    cx = SPINE_X + SPINE_W / 2   # spine centre-line for arrows

    ax.text(0.5, 0.972, "M1 agent - shipped decision path", ha="center",
            fontsize=15, fontweight="bold", color=INK)
    ax.text(0.5, 0.949,
            "Every box maps to real code in main.py / src/baseline.py.",
            ha="center", fontsize=8.4, color=MUTED)

    GAP = 0.021
    y = 0.928

    # 1. input
    y = box(ax, SPINE_X, y, SPINE_W, [
        "obs_dict  from the cabt engine",
        "active . bench . energies . hand . deck . prizes . legal options",
    ], "#eef4fc", BLUE, fontsize=8.4)

    # side: legality (fixed y, chosen so side callouts never collide)
    box(ax, SIDE_X, 0.928, SIDE_W, [
        "Legality is the ENGINE's job",
        "select[\"option\"] holds only legal moves;",
        "the agent ranks them, never re-derives",
        "legality. (RULES: engine_filters_legality)",
    ], "#f7f7f5", GREY, fontsize=7.4, align="left", textcolor=INK2)
    arrow(ax, SIDE_X, 0.893, SPINE_X + SPINE_W, 0.893, color=GREY, style="-", ls="--")

    arrow(ax, cx, y, cx, y - GAP)
    y -= GAP

    # 2. safety wrapper
    y = box(ax, SPINE_X, y, SPINE_W, [
        "main.agent(obs_dict)  -  try/except, can never raise",
    ], "#fdeeea", ORANGE, fontsize=8.6, weight="bold")

    # side: deck selection branch
    box(ax, SIDE_X, 0.805, SIDE_W, [
        "select is None  ->  deck-selection turn:",
        "return the 60 card IDs from deck.csv",
    ], "#f7f7f5", GREY, fontsize=7.4, align="left", textcolor=INK2)
    arrow(ax, SPINE_X + SPINE_W, y + 0.023, SIDE_X, y + 0.023,
          color=GREY, ls="--")

    arrow(ax, cx, y, cx, y - GAP)
    y -= GAP

    # 3. gate 1 header
    y = box(ax, SPINE_X, y, SPINE_W, [
        "GATE 1 . hard_override()  -  fires before any scoring",
    ], "#fdecec", CRITICAL, fontsize=8.6, weight="bold")

    y -= MIN_GAP
    # 4. gate 1 rules
    y = box(ax, SPINE_X, y, SPINE_W, [
        "Rule 1   Lethal that ENDS the game  ->  take it",
        "Rule 2   Trade up: KO their 2-3 prize Pokemon with our 1-prize",
        "Rule 3   Never retreat into a free KO if a safe bench slot exists",
    ], "#ffffff", CRITICAL, fontsize=7.9, align="left")

    # side: damage model
    box(ax, SIDE_X, 0.723, SIDE_W, [
        "Damage model  (_guaranteed_damage)",
        "",
        "dmg = attack.damage   <- coin-independent",
        "                         FLOOR, never an estimate",
        "weakness match   ->  dmg x 2",
        "resistance match ->  dmg - 30",
        "",
        "Cited to the engine's own C++ source",
        "(SetProperty.h:320-338), not the rulebook.",
        "Can miss a coin-flip lethal; never invents one.",
    ], "#f0f9f5", AQUA, fontsize=7.3, align="left")

    arrow(ax, cx, y, cx, y - GAP)
    ax.text(cx + 0.012, y - GAP / 2, "no rule fired", fontsize=7.3,
            color=MUTED, va="center")
    y -= GAP

    # 5. gate 2 header
    y = box(ax, SPINE_X, y, SPINE_W, [
        "GATE 2 . baseline_score()  ->  argmax over legal options",
    ], "#eef4fc", BLUE, fontsize=8.6, weight="bold")

    y -= MIN_GAP
    # 6. score table
    y = box(ax, SPINE_X, y, SPINE_W, [
        "MAIN context - scalar score per option",
        "",
        "ATTACK          guaranteed_dmg / 100  (+ prize value if it KOs)",
        "PLAY supporter  0.70 if few other plays, else 0.50",
        "EVOLVE          0.60          PLAY basic   0.45",
        "ATTACH          0.40          PLAY item    0.35",
        "ABILITY         0.30          END turn     0.00",
        "RETREAT         0.30 if active HP < 30%, else -0.10",
        "DISCARD        -0.20",
        "",
        "SWITCH / TO_ACTIVE  ->  by bench HP fraction",
        "EFFECT_TARGET       ->  prize value + damage already taken",
    ], "#ffffff", BLUE, fontsize=7.5, align="left")

    # side: fallback ladder
    box(ax, SIDE_X, 0.487, SIDE_W, [
        "Never-raise fallback ladder",
        "",
        "1.  src.baseline.choose(obs)",
        "        | exception -> logged to stderr",
        "2.  uniform random LEGAL option",
        "        | exception -> logged to stderr",
        "3.  _legal_fallback(obs)  - stdlib only",
        "",
        "Measured: 0 crashes, 0 fallbacks fired",
        "across the ladder run and full local suite.",
    ], "#fdeeea", ORANGE, fontsize=7.3, align="left")

    arrow(ax, cx, y, cx, y - GAP)
    y -= GAP

    # 7. output
    y = box(ax, SPINE_X, y, SPINE_W, [
        "selection : list[int]  -  indices into the legal option list",
    ], "#f0f9f5", AQUA, fontsize=8.6, weight="bold")

    # emergent-ordering note (side column, below the fallback ladder)
    ax.text(SIDE_X, 0.238,
            "Emergent priority: any attack over\n"
            "70 damage outranks every non-attack\n"
            "action. Energy attachment is NOT\n"
            "unconditionally first - board damage\n"
            "wins ties.",
            fontsize=7.4, color=INK2, va="top", ha="left", linespacing=1.7)

    # footer, placed relative to the last spine box
    ax.text(0.5, y - 0.085,
            "Cold-start latency from the packaged submission, full game:\n"
            "mean 0.027 ms . p95 0.075 ms . max 0.259 ms per decision. "
            "Zero third-party imports on this path.",
            ha="center", va="top", fontsize=7.7, color=INK2, linespacing=1.7)
    ax.text(0.5, y - 0.143,
            "Deliberately absent: lookahead search (the engine exposes no state-copy API -\n"
            "0/20 replay trials reproduced a position), opponent modelling, and a learned\n"
            "evaluator (one was built, validated, and rejected on the numbers).",
            ha="center", va="top", fontsize=7.4, color=MUTED, linespacing=1.7)

    fig.savefig(os.path.join(OUT_DIR, "architecture.png"), dpi=DPI,
                facecolor=SURFACE)
    plt.close(fig)
    print("wrote architecture.png")


if __name__ == "__main__":
    build()
