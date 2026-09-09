"""Regression test for Step 4 of the value-net proposal
(docs/writeup/ablation_log.md). Step 4's blend was rejected (no w beat
control by a margin distinguishable from noise -- see the ablation log),
so src/baseline.py was reverted to the pure control and the blend code
lives on only as an archived candidate,
docs/writeup/rejected/value_net_blend.py -- the same convention every
other rejected ablation candidate (A-F) already uses. This test loads that
archived file directly (not src.baseline) and validates the two hard
properties that had to hold before the win-rate sweep could be trusted:

  1. w=0.0 (the default) must reproduce docs/writeup/baseline_control.py's
     SWITCH-context scoring EXACTLY -- same choices, same scores, on real
     games. This is checked directly against the frozen control file (never
     modified per the task constraints), not just asserted from reading the
     code.
  2. Every w in {0, 0.25, 0.5, 0.75, 1.0} must run crash-free even if the
     value-net checkpoint is missing (graceful heuristic-only fallback).

Run with: python tests/test_value_net_blend.py [n_games]
"""

import importlib.util
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from cg import game as cg_game  # noqa: E402
from main import read_deck_csv  # noqa: E402

MAX_STEPS_PER_GAME = 4000

spec = importlib.util.spec_from_file_location(
    "baseline_control", os.path.join(REPO_ROOT, "docs", "writeup", "baseline_control.py")
)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)

spec2 = importlib.util.spec_from_file_location(
    "value_net_blend", os.path.join(REPO_ROOT, "docs", "writeup", "rejected", "value_net_blend.py")
)
baseline = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(baseline)


def play_and_compare(deck0: list[int], deck1: list[int]) -> int:
    """Plays one game feeding IDENTICAL selections to both baseline.choose()
    (w=0) and control.choose(), asserting they agree at every decision.
    Returns the number of decisions compared."""
    obs, start_data = cg_game.battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(
            f"battle_start failed: errorPlayer={start_data.errorPlayer} errorType={start_data.errorType}"
        )
    steps = 0
    compared = 0
    try:
        while obs["current"]["result"] == -1:
            steps += 1
            if steps > MAX_STEPS_PER_GAME:
                raise RuntimeError("game exceeded MAX_STEPS_PER_GAME")
            sel_candidate = baseline.choose(obs)
            sel_control = control.choose(obs)
            compared += 1
            assert sel_candidate == sel_control, (
                f"step {steps}: w=0 selection {sel_candidate} != control selection "
                f"{sel_control} for context {obs['select']['context']}"
            )
            obs = cg_game.battle_select(sel_candidate)
        return compared
    finally:
        cg_game.battle_finish()


def test_w0_matches_control(n_games: int) -> None:
    assert baseline.VALUE_NET_WEIGHT == 0.0, "default VALUE_NET_WEIGHT must be 0.0"
    deck = read_deck_csv()
    total_compared = 0
    for i in range(n_games):
        total_compared += play_and_compare(deck, deck)
    print(f"w=0 vs control: {n_games} games, {total_compared} decisions, all identical. PASS.")


def test_all_weights_crash_free(n_games: int) -> None:
    deck = read_deck_csv()
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):
        baseline.VALUE_NET_WEIGHT = w
        exceptions = 0
        for i in range(n_games):
            obs, sd = cg_game.battle_start(deck, deck)
            steps = 0
            try:
                while obs["current"]["result"] == -1 and steps < MAX_STEPS_PER_GAME:
                    steps += 1
                    obs = cg_game.battle_select(baseline.choose(obs))
            except Exception as e:
                exceptions += 1
                print(f"  [w={w} game {i}] EXCEPTION: {type(e).__name__}: {e}")
            finally:
                cg_game.battle_finish()
        assert exceptions == 0, f"w={w}: {exceptions}/{n_games} games raised an exception"
        print(f"w={w}: {n_games} games, 0 exceptions. PASS.")
    baseline.VALUE_NET_WEIGHT = 0.0


def test_missing_checkpoint_falls_back_gracefully(n_games: int) -> None:
    real_net = baseline._VALUE_NET
    real_attempted = baseline._VALUE_NET_LOAD_ATTEMPTED
    baseline._VALUE_NET = None
    baseline._VALUE_NET_LOAD_ATTEMPTED = True  # pretend load already happened and failed
    baseline.VALUE_NET_WEIGHT = 0.5
    deck = read_deck_csv()
    exceptions = 0
    try:
        for i in range(n_games):
            obs, sd = cg_game.battle_start(deck, deck)
            steps = 0
            try:
                while obs["current"]["result"] == -1 and steps < MAX_STEPS_PER_GAME:
                    steps += 1
                    obs = cg_game.battle_select(baseline.choose(obs))
            except Exception as e:
                exceptions += 1
                print(f"  [missing-ckpt game {i}] EXCEPTION: {type(e).__name__}: {e}")
            finally:
                cg_game.battle_finish()
    finally:
        baseline._VALUE_NET = real_net
        baseline._VALUE_NET_LOAD_ATTEMPTED = real_attempted
        baseline.VALUE_NET_WEIGHT = 0.0
    assert exceptions == 0, f"{exceptions}/{n_games} games raised an exception with a missing checkpoint"
    print(f"missing checkpoint, w=0.5: {n_games} games, 0 exceptions (graceful fallback). PASS.")


def main() -> None:
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    test_w0_matches_control(n_games)
    test_all_weights_crash_free(n_games)
    test_missing_checkpoint_falls_back_gracefully(n_games)
    print("\nALL PASS")


if __name__ == "__main__":
    main()
