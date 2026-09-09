"""Builds the Media Gallery figures for the Strategy Writeup. Every number
plotted here is copy-verified against docs/writeup/ablation_log.md,
deck.csv, or a live `kaggle competitions submissions` check -- see the
inventory in the conversation this script was written from. Nothing here
is invented, estimated, or interpolated; where real paired data doesn't
exist (figure 3), the chart shows exactly the real points that exist and
says so, rather than filling a gap.

Palette: skill-validated (references/palette.md, node
scripts/validate_palette.js) -- categorical slots 1/2/3 (blue/orange/aqua)
for genuinely distinct entities (figure 2), the fixed "critical" status
red for the six rejected ablation candidates (figure 1, all same outcome),
muted grey for "not applicable / not tested" (never a fabricated bar).
"""

import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- palette (docs: dataviz skill references/palette.md) ------------------
SURFACE = "#FFFFFF"  # explicit white background per spec
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

SLOT_BLUE = "#2a78d6"
SLOT_ORANGE = "#eb6834"
SLOT_AQUA = "#1baf7a"

STATUS_CRITICAL = "#d03b3b"
STATUS_GOOD = "#0ca30c"
NOT_TESTED_GREY = "#c3c2b7"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "text.color": INK_PRIMARY,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_SECONDARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})

DPI = 200
WIDTH_IN = 1600 / DPI  # = 8.0in -> 1600px wide at this dpi


def se_binomial(p=0.5, n=300):
    return math.sqrt(p * (1 - p) / n)


def style_axes(ax, y_is_pct=True):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    if y_is_pct:
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))


# =============================================================================
# Figure 1: ablation.png
# =============================================================================

def build_ablation():
    # Source: docs/writeup/ablation_log.md "Final summary" table, each at n=300
    # games vs baseline_control.py.
    candidates = ["A", "B", "C", "D", "E", "F"]
    win_rate = [45.7, None, 31.3, 52.3, 49.3, 50.7]  # None = not tested
    counts = ["137/300", "not tested", "94/300", "157/300", "148/300", "152/300"]
    labels_short = {
        "A": "3 unhandled\ncontexts",
        "B": "KO-first\nattack sel.",
        "C": "Role-aware\nenergy attach",
        "D": "Retreat\ngating",
        "E": "Supporter\nordering",
        "F": "Never pass\nattack for END",
    }

    fig, ax = plt.subplots(figsize=(WIDTH_IN, 5.9), dpi=DPI)

    n = 300
    se = se_binomial(0.5, n) * 100  # in percentage points
    noise_lo, noise_hi = 50 - 2 * se, 50 + 2 * se
    ax.axhspan(noise_lo, noise_hi, color=BASELINE, alpha=0.25, zorder=1,
               label=f"~95% noise band at n=300 ({noise_lo:.1f}-{noise_hi:.1f}%)")
    ax.axhline(50, color=INK_MUTED, linewidth=1, linestyle=":", zorder=2)
    ax.axhline(53, color=INK_SECONDARY, linewidth=1.5, linestyle="--", zorder=2,
               label="accept threshold (53%)")

    x = range(len(candidates))
    bar_w = 0.6
    for i, (cand, wr) in enumerate(zip(candidates, win_rate)):
        if wr is None:
            placeholder_h = 3  # not a data value -- just tall enough to place the N/A label
            ax.bar(i, placeholder_h, width=bar_w, bottom=0, color="none",
                   edgecolor=NOT_TESTED_GREY, hatch="////", linewidth=1.2, zorder=3)
            ax.text(i, placeholder_h + 1, "N/A", ha="center", va="bottom", fontsize=9,
                    color=INK_MUTED, zorder=4)
        else:
            # per-candidate exact SE, using its own logged win count
            wins = int(counts[i].split("/")[0])
            p = wins / n
            se_i = math.sqrt(p * (1 - p) / n) * 100
            ax.bar(i, wr, width=bar_w, color=STATUS_CRITICAL, zorder=3)
            ax.errorbar(i, wr, yerr=se_i, color=INK_PRIMARY, capsize=4,
                        linewidth=1.2, zorder=4)
            # Label placed INSIDE the bar (not above the error-bar cap) so
            # adjacent close-valued bars (D/E/F all land near 50-52%) never
            # collide with each other or with the threshold/legend area.
            ax.text(i, wr * 0.5, f"{wr:.1f}%", ha="center", va="center",
                    fontsize=10, color="white", fontweight="bold", zorder=5)

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{c}\n{labels_short[c]}" for c in candidates], fontsize=8.5)
    ax.set_ylim(0, 65)
    ax.set_ylabel("Win rate vs. frozen control (n=300)")
    style_axes(ax)

    # Title, legend, and caption all placed in fixed figure-fraction
    # coordinates (fig.text / fig.legend), not axes-relative bbox_to_anchor
    # or suptitle's own y -- both can silently clip off-canvas when they
    # interact with tight_layout's rect. This way every element's position
    # is guaranteed inside [0, 1] regardless of layout engine behavior.
    fig.text(0.5, 0.97, "Six single-change ablation candidates — all six rejected",
              ha="center", fontsize=13, fontweight="bold", color=INK_PRIMARY)

    critical_patch = mpatches.Patch(color=STATUS_CRITICAL, label="Tested, rejected (5)")
    na_patch = mpatches.Patch(facecolor="none", edgecolor=NOT_TESTED_GREY, hatch="////",
                               label="Not tested — already satisfied in control (B)")
    handles, _ = ax.get_legend_handles_labels()
    fig.legend(handles=[critical_patch, na_patch] + handles, loc="upper center",
               bbox_to_anchor=(0.5, 0.905), ncol=2, fontsize=8, frameon=False)

    fig.text(0.5, 0.01,
              "Error bars: exact binomial SE per candidate's own logged win count. "
              "C is a root-caused regression (real bug); D/E/A sit inside the noise band; "
              "F is a proven structural no-op. See docs/writeup/ablation_log.md.",
              ha="center", fontsize=7.5, color=INK_MUTED, wrap=True)

    fig.tight_layout(rect=(0, 0.045, 1, 0.82))
    path = os.path.join(OUT_DIR, "ablation.png")
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"wrote {path}")


# =============================================================================
# Figure 2: ladder.png
# =============================================================================

def build_ladder():
    # Source: `kaggle competitions submissions -c pokemon-tcg-ai-battle`,
    # live-verified.
    labels = ["M0\n(random legal)", "M1\n(rule-based)", "M1 + redesigned deck"]
    scores = [306.0, 475.1, 256.1]
    colors = [SLOT_BLUE, SLOT_ORANGE, SLOT_AQUA]

    fig, ax = plt.subplots(figsize=(WIDTH_IN, 5.2), dpi=DPI)
    bars = ax.bar(labels, scores, color=colors, width=0.55, zorder=3)
    for b, s in zip(bars, scores):
        ax.text(b.get_x() + b.get_width() / 2, s + 8, f"{s:.1f}",
                ha="center", va="bottom", fontsize=12, fontweight="bold",
                color=INK_PRIMARY, zorder=4)

    ax.set_ylim(0, max(scores) * 1.18)
    ax.set_ylabel("Live public ladder score")
    ax.set_title("Live Kaggle ladder score — a moving target, not a final result",
                 fontsize=13, fontweight="bold", color=INK_PRIMARY, pad=14)
    style_axes(ax, y_is_pct=False)
    ax.tick_params(axis="x", labelsize=9.5)

    fig.text(0.5, 0.01,
              "Public score, most recently confirmed live via `kaggle competitions "
              "submissions`. This is a live Gaussian rating and will keep moving.",
              ha="center", fontsize=8, color=INK_MUTED)

    fig.tight_layout(rect=(0, 0.05, 1, 1))
    path = os.path.join(OUT_DIR, "ladder.png")
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"wrote {path}")


# =============================================================================
# Figure 3: local_vs_ladder.png (THE key figure — only 2 real paired points)
# =============================================================================

def build_local_vs_ladder():
    # Source: docs/writeup/outline.md §5 table + live ladder check. Only two
    # variants have BOTH a local win rate and a live ladder score -- M0 has
    # no comparable local win-rate metric (only a legality check), and the
    # ablation/value-net candidates were never submitted to the ladder.
    points = [
        ("M1 (rule-based)", 91.5, 475.1, SLOT_ORANGE),
        ("M1 + redesigned deck", 88.5, 256.1, SLOT_AQUA),
    ]

    fig, ax = plt.subplots(figsize=(WIDTH_IN, 5.8), dpi=DPI)

    for name, local, ladder, color in points:
        ax.scatter([local], [ladder], s=220, color=color, zorder=4,
                   edgecolor=INK_PRIMARY, linewidth=1.2)
        ax.annotate(f"{name}\nlocal {local:.1f}% · live {ladder:.1f}",
                    (local, ladder), textcoords="offset points",
                    xytext=(14, 10), fontsize=9.5, color=INK_PRIMARY)

    # Explicit connecting line (NOT a fitted trend line -- two points always
    # "fit" trivially; this is drawn only to show the direction of change
    # between the two real, named variants, labeled as such).
    xs = [p[1] for p in points]
    ys = [p[2] for p in points]
    ax.plot(xs, ys, color=INK_MUTED, linestyle="--", linewidth=1.3, zorder=2)
    ax.annotate("", xy=(xs[1], ys[1]), xytext=(xs[0], ys[0]),
                arrowprops=dict(arrowstyle="->", color=INK_MUTED, lw=1.3))

    ax.set_xlim(80, 100)
    ax.set_ylim(200, 520)
    ax.set_xlabel("Local win rate vs. weak local opponent (%)")
    ax.set_ylabel("Live ladder score")
    ax.set_title("Local evaluation did not predict live ladder performance",
                 fontsize=13, fontweight="bold", color=INK_PRIMARY, pad=14)
    style_axes(ax, y_is_pct=False)

    fig.text(0.5, 0.06,
              "Only 2 of the project's variants have BOTH a local win rate and a "
              "live ladder score — this is not a sampled distribution, it is the "
              "complete set. Nearly identical local performance (91.5% vs 88.5%) "
              "produced a ~219-point live-score gap.",
              ha="center", fontsize=8, color=INK_MUTED, wrap=True)

    fig.tight_layout(rect=(0, 0.11, 1, 1))
    path = os.path.join(OUT_DIR, "local_vs_ladder.png")
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"wrote {path}")


# =============================================================================
# Figure 4: valuenet.png (two panels: held-out accuracy, blend sweep)
# =============================================================================

def build_valuenet():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDTH_IN, 5.4), dpi=DPI)

    # Panel A: held-out accuracy vs constant-predictor baseline.
    # Source: ablation_log.md Step 3 result table (n=5,799 held-out positions,
    # game-level split, 50 unseen games).
    labels_a = ["Value net", "Constant-\npredictor\nbaseline"]
    vals_a = [62.32, 51.63]
    colors_a = [SLOT_BLUE, NOT_TESTED_GREY]
    bars = ax1.bar(labels_a, vals_a, color=colors_a, width=0.55, zorder=3)
    for b, v in zip(bars, vals_a):
        ax1.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.2f}%",
                  ha="center", fontsize=11, fontweight="bold", color=INK_PRIMARY)
    ax1.set_ylim(0, 80)
    ax1.set_ylabel("Held-out accuracy")
    ax1.set_title("A. Value net: real signal\n(n=5,799 held-out positions, game-level split)",
                  fontsize=10.5, color=INK_PRIMARY)
    style_axes(ax1)

    # Panel B: blend sweep. Source: ablation_log.md Step 4 sweep table, n=300
    # each vs baseline_control.py.
    ws = [0.0, 0.25, 0.5, 0.75, 1.0]
    wr = [53.3, 49.0, 45.3, 54.0, 51.0]
    n = 300
    se = se_binomial(0.5, n) * 100
    noise_lo, noise_hi = 50 - 2 * se, 50 + 2 * se
    ax2.axhspan(noise_lo, noise_hi, color=BASELINE, alpha=0.25, zorder=1,
                label=f"~95% noise band ({noise_lo:.1f}-{noise_hi:.1f}%)")
    ax2.axhline(53, color=INK_SECONDARY, linewidth=1.3, linestyle="--", zorder=2,
                label="accept threshold (53%)")
    ax2.plot(ws, wr, color=SLOT_BLUE, marker="o", markersize=7,
             linewidth=1.8, zorder=3)
    for w, r in zip(ws, wr):
        ax2.annotate(f"{r:.1f}%", (w, r), textcoords="offset points",
                     xytext=(0, 9), ha="center", fontsize=8.5, color=INK_PRIMARY)
    ax2.annotate("w=0.0 is byte-identical to control —\nthis 53.3% is proven pure noise",
                 xy=(0.02, 0.08), xycoords="axes fraction",
                 fontsize=7.3, color=INK_MUTED, ha="left", va="bottom")
    ax2.set_xticks(ws)
    ax2.set_xlabel("Blend weight w  (0 = pure heuristic, 1 = pure value net)")
    ax2.set_ylabel("Win rate vs. control (n=300 each)")
    ax2.set_ylim(35, 65)
    ax2.set_title("B. Blend sweep: no weight beats control\noutside noise — no dose-response trend",
                  fontsize=10.5, color=INK_PRIMARY)
    ax2.legend(loc="lower right", fontsize=7.5, frameon=False)
    style_axes(ax2)

    fig.text(0.5, 0.97, "Value-net episode: a real training signal that didn't translate to win rate",
              ha="center", fontsize=12.5, fontweight="bold", color=INK_PRIMARY)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    path = os.path.join(OUT_DIR, "valuenet.png")
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"wrote {path}")


# =============================================================================
# Figure 5: deck.png
# =============================================================================

def build_deck():
    # Source: deck.csv (verified card-by-card), all_card_data() for HP/weak/
    # retreat cost. NOTE: task description said "28 trainers" -- the actual
    # deck has 32; category totals below are computed from deck.csv directly.
    pokemon = [("Throh", 4), ("Landorus", 4), ("Terrakion", 4)]
    trainers = [
        ("Cheren", 4), ("Ultra Ball", 4), ("Fighting Gong", 4), ("Switch", 4),
        ("Premium Power Pro", 4), ("Poke Pad", 4), ("Lively Stadium", 4),
        ("Boxed Order", 2), ("Crushing Hammer", 2),
    ]
    energy = [("Basic Fighting Energy", 16)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDTH_IN, 6.0), dpi=DPI,
                                    gridspec_kw={"width_ratios": [1, 1.6]})

    # Panel A: category composition (12 / 32 / 16 = 60).
    cat_labels = ["Pokemon\n(12)", "Trainers\n(32)", "Energy\n(16)"]
    cat_counts = [12, 32, 16]
    cat_colors = [SLOT_BLUE, SLOT_ORANGE, SLOT_AQUA]
    bars = ax1.bar(cat_labels, cat_counts, color=cat_colors, width=0.55, zorder=3)
    for b, c in zip(bars, cat_counts):
        ax1.text(b.get_x() + b.get_width() / 2, c + 0.8, str(c), ha="center",
                  fontsize=12, fontweight="bold", color=INK_PRIMARY)
    ax1.set_ylim(0, 38)
    ax1.set_ylabel("Cards (of 60)")
    ax1.set_title("A. Composition", fontsize=11, color=INK_PRIMARY)
    style_axes(ax1, y_is_pct=False)

    # Panel B: individual cards, colored by category, sorted by category
    # then count.
    all_cards = (
        [(n, c, SLOT_BLUE, "Pokemon") for n, c in pokemon]
        + [(n, c, SLOT_ORANGE, "Trainer") for n, c in trainers]
        + [(n, c, SLOT_AQUA, "Energy") for n, c in energy]
    )
    names = [c[0] for c in all_cards]
    counts = [c[1] for c in all_cards]
    colors = [c[2] for c in all_cards]
    y = range(len(all_cards))
    ax2.barh(list(y), counts, color=colors, height=0.62, zorder=3)
    ax2.set_yticks(list(y))
    ax2.set_yticklabels(names, fontsize=8.5)
    ax2.invert_yaxis()
    for yi, c in zip(y, counts):
        ax2.text(c + 0.3, yi, str(c), va="center", fontsize=8.5, color=INK_PRIMARY)
    ax2.set_xlim(0, 18)
    ax2.set_xlabel("Copies in deck")
    ax2.set_title("B. Every card (all-Basic, single-prize, mono-Fighting)",
                  fontsize=11, color=INK_PRIMARY)
    style_axes(ax2, y_is_pct=False)
    ax2.grid(axis="x", color=GRIDLINE, linewidth=1, zorder=0)
    ax2.grid(axis="y", visible=False)

    legend_handles = [
        mpatches.Patch(color=SLOT_BLUE, label="Pokemon (all Basic)"),
        mpatches.Patch(color=SLOT_ORANGE, label="Trainer"),
        mpatches.Patch(color=SLOT_AQUA, label="Energy"),
    ]
    ax2.legend(handles=legend_handles, loc="upper right", fontsize=8, frameon=False)

    fig.text(0.5, 0.97, "Deck: 60 cards, built for a greedy per-turn policy with no setup planning",
              ha="center", fontsize=12.5, fontweight="bold", color=INK_PRIMARY)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    path = os.path.join(OUT_DIR, "deck.png")
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"wrote {path}")


if __name__ == "__main__":
    build_ablation()
    build_ladder()
    build_local_vs_ladder()
    build_valuenet()
    build_deck()
