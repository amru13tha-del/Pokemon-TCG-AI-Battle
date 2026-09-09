"""Regression test for Step 2 of the value-net proposal
(docs/writeup/ablation_log.md): validates src/switch_predict.py's
predicted post-retreat position against the REAL engine's actual
resulting position, for real games. This is the substitute for true
state-copying (proven impossible in Step 1, see tests/test_state_copy.py):
since retreat is deterministic and fully visible, we predict BEFORE acting,
then actually act, and diff the real result against the prediction --
no branching required.

Compares src/value_features.py's feature vector (order-invariant, the same
representation the value net will actually consume) rather than a raw dict
diff, since exact bench-slot ordering isn't something the value net needs
and isn't part of the documented prediction contract.

Run with: python tests/test_switch_prediction.py [n_games]
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import numpy as np  # noqa: E402

from cg import game as cg_game  # noqa: E402
from main import read_deck_csv  # noqa: E402
from src.baseline import choose  # noqa: E402
from src.switch_predict import predict_post_switch  # noqa: E402
from src.value_features import position_features  # noqa: E402

MAX_STEPS_PER_GAME = 4000
SWITCH_CONTEXT = 3  # SelectContext.SWITCH -- voluntary retreat target selection
TOLERANCE = 1e-5


def play_one_game(deck0: list[int], deck1: list[int]) -> tuple[list[dict], int]:
    """Returns (mismatch records, count of SWITCH decisions seen)."""
    obs, start_data = cg_game.battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(
            f"battle_start failed: errorPlayer={start_data.errorPlayer} errorType={start_data.errorType}"
        )
    steps = 0
    mismatches = []
    switch_count = 0
    try:
        while obs["current"]["result"] == -1:
            steps += 1
            if steps > MAX_STEPS_PER_GAME:
                raise RuntimeError("game exceeded MAX_STEPS_PER_GAME")
            select = obs["select"]
            your_index = obs["current"]["yourIndex"]
            selection = choose(obs)

            if select["context"] == SWITCH_CONTEXT:
                switch_count += 1
                options = select["option"]
                bench_target_idx = options[selection[0]].get("index")
                predicted = predict_post_switch(obs, your_index, bench_target_idx)
                predicted_features = position_features(predicted, your_index)

                obs_after = cg_game.battle_select(selection)
                actual_features = position_features(obs_after, your_index)

                diff = np.abs(predicted_features - actual_features)
                if np.any(diff > TOLERANCE):
                    mismatches.append({
                        "step": steps,
                        "bench_target_idx": bench_target_idx,
                        "predicted": predicted_features.tolist(),
                        "actual": actual_features.tolist(),
                        "max_diff": float(diff.max()),
                    })
                obs = obs_after
            else:
                obs = cg_game.battle_select(selection)
        return mismatches, switch_count
    finally:
        cg_game.battle_finish()


def main() -> None:
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    deck = read_deck_csv()

    exceptions = 0
    total_switch_decisions = 0
    all_mismatches = []
    for i in range(n_games):
        try:
            mismatches, switch_count = play_one_game(deck, deck)
            total_switch_decisions += switch_count
            for m in mismatches:
                all_mismatches.append((i, m))
        except Exception as e:
            exceptions += 1
            print(f"[game {i}] EXCEPTION: {type(e).__name__}: {e}")

    assert exceptions == 0, f"{exceptions} game(s) raised an exception (crash or illegal action)"

    print(f"total SWITCH decisions observed: {total_switch_decisions} across {n_games} games")
    assert total_switch_decisions > 0, (
        "0 SWITCH decisions occurred -- this test would pass vacuously. "
        "Increase n_games or check that voluntary retreats are actually happening."
    )

    for game_i, m in all_mismatches[:10]:
        print(f"[game {game_i} step {m['step']}] MISMATCH target={m['bench_target_idx']} "
              f"max_diff={m['max_diff']:.4f}")
        print(f"  predicted: {m['predicted']}")
        print(f"  actual:    {m['actual']}")

    assert not all_mismatches, (
        f"{len(all_mismatches)} SWITCH decision(s) across {n_games} games had a "
        "predicted-vs-actual feature mismatch -- predict_post_switch() does not "
        "faithfully model the real engine's retreat rules"
    )
    print(f"PASS: {n_games} games, 0 exceptions, 0 prediction mismatches "
          f"on SWITCH decisions (context={SWITCH_CONTEXT}).")


if __name__ == "__main__":
    main()
