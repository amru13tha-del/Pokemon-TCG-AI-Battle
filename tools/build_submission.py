"""Build submission.tar.gz: main.py + deck.csv + cg/ + src/ at the archive top level.

Validates deck.csv before packing:
  - exactly 60 entries
  - every ID resolves in "docs/official/EN Card Data.csv"
  - at most 4 copies of any card name, except cards whose category is Basic Energy
  - at most 1 copy of any ACE SPEC card (checked against the live engine's
    CardData.aceSpec, since the CSV has no such column)
  - has a Basic Pokémon
"""

import csv
import os
import sys
import tarfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD_DATA_PATH = os.path.join(REPO_ROOT, "docs", "official", "EN Card Data.csv")
DECK_PATH = os.path.join(REPO_ROOT, "deck.csv")
MAIN_PATH = os.path.join(REPO_ROOT, "main.py")
CG_DIR = os.path.join(REPO_ROOT, "cg")
SRC_DIR = os.path.join(REPO_ROOT, "src")
OUT_PATH = os.path.join(REPO_ROOT, "submission.tar.gz")

sys.path.insert(0, REPO_ROOT)
from cg.api import all_card_data  # noqa: E402


STAGE_TYPE_COLUMN = "Stage (Pokémon)/Type (Energy and Trainer)"


def load_card_names() -> dict[int, tuple[str, str]]:
    """card_id -> (name, stage_or_type)"""
    cards = {}
    with open(CARD_DATA_PATH, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cards[int(row["Card ID"])] = (row["Card Name"], row[STAGE_TYPE_COLUMN])
    return cards


def read_deck() -> list[int]:
    with open(DECK_PATH, "r") as f:
        lines = f.read().split("\n")
    lines = [ln for ln in (l.strip() for l in lines) if ln != ""]
    if len(lines) != 60:
        sys.exit(f"deck.csv must have exactly 60 entries, found {len(lines)}")
    try:
        return [int(x) for x in lines]
    except ValueError as e:
        sys.exit(f"deck.csv contains a non-integer card ID: {e}")


def validate_deck(deck: list[int], cards: dict[int, tuple[str, str]]) -> None:
    unresolved = sorted({cid for cid in deck if cid not in cards})
    if unresolved:
        sys.exit(f"deck.csv has {len(unresolved)} card ID(s) not present in EN Card Data.csv: {unresolved}")

    counts: dict[str, int] = {}
    for cid in deck:
        name, stage_or_type = cards[cid]
        if stage_or_type == "Basic Energy":
            continue
        counts[name] = counts.get(name, 0) + 1
    over_limit = {name: n for name, n in counts.items() if n > 4}
    if over_limit:
        sys.exit(f"deck.csv exceeds 4 copies of a non-basic-Energy card: {over_limit}")

    ace_spec_ids = {c.cardId for c in all_card_data() if c.aceSpec}
    ace_spec_counts: dict[int, int] = {}
    for cid in deck:
        if cid in ace_spec_ids:
            ace_spec_counts[cid] = ace_spec_counts.get(cid, 0) + 1
    ace_over_limit = {cid: n for cid, n in ace_spec_counts.items() if n > 1}
    if ace_over_limit:
        sys.exit(f"deck.csv has more than 1 copy of an ACE SPEC card: "
                  f"{ {cards[cid][0]: n for cid, n in ace_over_limit.items()} }")

    has_basic_pokemon = any(cards[cid][1] == "Basic Pokémon" for cid in deck)
    if not has_basic_pokemon:
        sys.exit("deck.csv has no Basic Pokémon.")

    print(f"Deck OK: 60 cards, {len(counts)} distinct non-Energy cards, all IDs resolve, "
          f"has a Basic Pokémon, no ACE SPEC over-count.")


# Files under src/ that exist as tested-but-unwired experiment artifacts
# (see docs/writeup/ablation_log.md, "Learned value-net proposal") -- not
# imported by src/baseline.py or anything reachable from main.agent, and
# value_features.py / value_net.py pull in numpy, which the reachable path
# otherwise never needs. Excluded from the shipped package: no reason to
# bundle unreachable code (or its unused dependency) into the submission.
SRC_EXCLUDE = {"value_features.py", "switch_predict.py", "value_net.py"}


def _add_package_dir(tar: tarfile.TarFile, src_dir: str, arc_dir: str, exclude: set[str] = frozenset()) -> list[str]:
    added = []
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            if fname.endswith(".pyc") or fname in exclude:
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, src_dir)
            arcname = os.path.join(arc_dir, rel)
            tar.add(full, arcname=arcname)
            added.append(arcname)
    return added


def build_archive() -> list[str]:
    manifest = ["main.py", "deck.csv"]
    with tarfile.open(OUT_PATH, "w:gz") as tar:
        tar.add(MAIN_PATH, arcname="main.py")
        tar.add(DECK_PATH, arcname="deck.csv")
        manifest += _add_package_dir(tar, CG_DIR, "cg")
        manifest += _add_package_dir(tar, SRC_DIR, "src", exclude=SRC_EXCLUDE)
    size_mb = os.path.getsize(OUT_PATH) / (1024 * 1024)
    print(f"Wrote {OUT_PATH} ({size_mb:.2f} MB)")
    print(f"\n{len(manifest)} files packaged:")
    for name in sorted(manifest):
        print(f"  {name}")
    return manifest


def main() -> None:
    cards = load_card_names()
    deck = read_deck()
    validate_deck(deck, cards)
    build_archive()


if __name__ == "__main__":
    main()
