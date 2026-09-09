"""M1 submission entrypoint: agent(obs_dict) -> list[int].

Three concentric safety nets, from best-play to zero-dependency:
  1. src.baseline.choose() -- hard overrides + heuristic scoring (see src/baseline.py).
  2. A uniformly random legal option (same strategy as the official sample agent).
  3. _legal_fallback() -- zero dependencies beyond the standard library and deck.csv.
Every path is wrapped so this can never raise and never return an illegal selection.
"""

import os
import random
import sys

DECK_PATH = "deck.csv"

try:
    from src.baseline import choose as _baseline_choose
except Exception:
    _baseline_choose = None


def _log_exception(context: str, exc: Exception) -> None:
    """Diagnostic only -- never affects which action is chosen, and must
    never itself raise (a logging failure can't be allowed to break the
    fallback path it's logging about)."""
    try:
        print(f"[agent fallback] {context}: {type(exc).__name__}: {exc}", file=sys.stderr)
    except Exception:
        pass


def _deck_file_path() -> str:
    if os.path.exists(DECK_PATH):
        return DECK_PATH
    return "/kaggle_simulations/agent/" + DECK_PATH


def read_deck_csv() -> list[int]:
    """Read deck.csv: 60 card IDs, one per line."""
    with open(_deck_file_path(), "r") as f:
        lines = f.read().split("\n")
    return [int(lines[i]) for i in range(60)]


def _legal_fallback(obs_dict: dict) -> list[int]:
    """Guaranteed-legal response for any context. Zero dependencies beyond
    the standard library and deck.csv, so it works even if everything else
    in this module is broken."""
    select = obs_dict.get("select")
    if select is None:
        return read_deck_csv()
    options = select.get("option") or []
    min_count = select.get("minCount", 0)
    max_count = select.get("maxCount", 0)
    k = max(0, min(max_count, len(options)))
    if k < min_count:
        k = min(min_count, len(options))
    return list(range(k))


def _random_legal(select: dict) -> list[int]:
    n_options = len(select["option"])
    return random.sample(range(n_options), select["maxCount"])


def _policy(obs_dict: dict) -> list[int]:
    select = obs_dict.get("select")
    if select is None:
        # Deck-selection context: return 60 card IDs, not option indices.
        return read_deck_csv()
    if _baseline_choose is not None:
        try:
            return _baseline_choose(obs_dict)
        except Exception as e:
            _log_exception("src.baseline.choose raised, falling back to random-legal", e)
    return _random_legal(select)


def agent(obs_dict: dict) -> list[int]:
    """Normal decision points -> option indices into obs_dict["select"]["option"].
    Deck-selection context (obs_dict["select"] is None) -> 60 card IDs.
    Must never raise. Must never exceed the per-move time budget.
    """
    try:
        return _policy(obs_dict)
    except Exception as e:
        _log_exception("_policy raised (unhandled), falling back to _legal_fallback", e)
        return _legal_fallback(obs_dict)
