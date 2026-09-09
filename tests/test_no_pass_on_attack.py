"""Regression test for Candidate F (docs/writeup/ablation_log.md): choose()
must never select END while a legal ATTACK option exists in the same
decision -- doing so permanently forfeits that turn's attack. Run with:
python tests/test_no_pass_on_attack.py [n_games]
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from cg import game as cg_game  # noqa: E402
from main import read_deck_csv  # noqa: E402
from src.baseline import choose  # noqa: E402

MAX_STEPS_PER_GAME = 4000
ATTACK_TYPE = 13
END_TYPE = 14


def play_one_game(deck0: list[int], deck1: list[int]) -> list[tuple]:
    """Returns a list of (step, selection, attack_indices, end_indices)
    violations -- empty if the invariant held for the whole game."""
    obs, start_data = cg_game.battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(
            f"battle_start failed: errorPlayer={start_data.errorPlayer} errorType={start_data.errorType}"
        )
    steps = 0
    violations = []
    try:
        while obs["current"]["result"] == -1:
            steps += 1
            if steps > MAX_STEPS_PER_GAME:
                raise RuntimeError("game exceeded MAX_STEPS_PER_GAME (possible infinite loop)")
            options = obs["select"]["option"]
            attack_indices = [i for i, o in enumerate(options) if o.get("type") == ATTACK_TYPE]
            end_indices = [i for i, o in enumerate(options) if o.get("type") == END_TYPE]
            selection = choose(obs)
            if attack_indices and selection and selection[0] in end_indices:
                violations.append((steps, list(selection), attack_indices, end_indices))
            obs = cg_game.battle_select(selection)
    finally:
        cg_game.battle_finish()
    return violations


def main() -> None:
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    deck = read_deck_csv()

    exceptions = 0
    all_violations = []
    for i in range(n_games):
        try:
            violations = play_one_game(deck, deck)
            for v in violations:
                all_violations.append((i, *v))
        except Exception as e:
            exceptions += 1
            print(f"[game {i}] EXCEPTION: {type(e).__name__}: {e}")

    assert exceptions == 0, f"{exceptions} game(s) raised an exception (crash or illegal action)"

    for game_i, step, selection, attack_idx, end_idx in all_violations[:20]:
        print(f"[game {game_i} step {step}] chose END {selection} while ATTACK legal at {attack_idx} (END at {end_idx})")

    assert not all_violations, (
        f"{len(all_violations)} decision(s) across {n_games} games chose END "
        "while a legal ATTACK option was available"
    )
    print(f"PASS: {n_games} games, 0 exceptions, 0 attack-vs-PASS violations.")


if __name__ == "__main__":
    main()
