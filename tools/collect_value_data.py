"""Step 3 data collection (docs/writeup/ablation_log.md, value-net
proposal): play M1-vs-M1 self-play games and label every MAIN-context
position with the eventual game outcome, from the perspective of whichever
player was to move at that decision.

"Every position" is operationalized as every MAIN-context decision
specifically, not every sub-decision (energy discard, hand-target picks,
etc.) -- MAIN is where "player to move" changes meaningfully turn to turn
(72.1% of all decisions per the Candidate-A instrumentation, ~117/game),
and src/value_features.py's feature vector only encodes board state, not
decision-context type, so training on MAIN-context snapshots specifically
vs. every micro-decision doesn't change what function is being learned --
only avoids diluting the dataset with near-duplicate snapshots taken
mid-resolution of a single compound action. Draw-outcome games are excluded
from labeling (no natural 0/1 label; rare enough not to matter).

Run with: python tools/collect_value_data.py [n_games] [out_path]
"""

import os
import sys
import time

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from cg import game as cg_game  # noqa: E402
from main import read_deck_csv  # noqa: E402
from src.baseline import choose  # noqa: E402
from src.value_features import FEATURE_DIM, position_features  # noqa: E402

MAX_STEPS_PER_GAME = 4000
MAIN_CONTEXT = 0


def play_one_game(deck0: list[int], deck1: list[int]) -> tuple[list[np.ndarray], list[int], int]:
    """Returns (feature vectors, mover_index per vector, final result)."""
    obs, start_data = cg_game.battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(
            f"battle_start failed: errorPlayer={start_data.errorPlayer} errorType={start_data.errorType}"
        )
    steps = 0
    features = []
    movers = []
    try:
        while obs["current"]["result"] == -1:
            steps += 1
            if steps > MAX_STEPS_PER_GAME:
                raise RuntimeError("game exceeded MAX_STEPS_PER_GAME")
            if obs["select"]["context"] == MAIN_CONTEXT:
                your_index = obs["current"]["yourIndex"]
                features.append(position_features(obs, your_index))
                movers.append(your_index)
            obs = cg_game.battle_select(choose(obs))
        return features, movers, obs["current"]["result"]
    finally:
        cg_game.battle_finish()


def main() -> None:
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 250
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO_ROOT, "data", "value_net", "positions.npz")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    deck = read_deck_csv()
    all_X = []
    all_y = []
    all_game_ids = []
    exceptions = 0
    draws_excluded = 0
    game_id = 0
    t0 = time.perf_counter()

    for i in range(n_games):
        try:
            features, movers, result = play_one_game(deck, deck)
        except Exception as e:
            exceptions += 1
            print(f"[game {i}] EXCEPTION: {type(e).__name__}: {e}")
            continue
        if result not in (0, 1):
            draws_excluded += 1
            continue
        for feat, mover in zip(features, movers):
            all_X.append(feat)
            all_y.append(1.0 if mover == result else 0.0)
            all_game_ids.append(game_id)
        game_id += 1
        if (i + 1) % 25 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  {i + 1}/{n_games} games, {len(all_X)} positions so far, {elapsed:.1f}s elapsed")

    X = np.stack(all_X).astype(np.float32) if all_X else np.zeros((0, FEATURE_DIM), dtype=np.float32)
    y = np.asarray(all_y, dtype=np.float32)
    game_ids = np.asarray(all_game_ids, dtype=np.int32)

    elapsed = time.perf_counter() - t0
    print(f"\n{n_games} games in {elapsed:.1f}s")
    print(f"exceptions: {exceptions}")
    print(f"draws excluded: {draws_excluded}")
    print(f"total labeled positions: {len(X)}  from {game_id} labeled games")
    print(f"label balance: {y.mean():.3f} positive (win) fraction")

    assert exceptions == 0, f"{exceptions} game(s) raised an exception during data collection"
    assert len(X) >= 20000, f"only {len(X)} positions collected, need >= 20000 -- increase n_games"

    np.savez(out_path, X=X, y=y, game_ids=game_ids)
    print(f"saved to {out_path}")


if __name__ == "__main__":
    main()
