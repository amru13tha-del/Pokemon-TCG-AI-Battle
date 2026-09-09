"""Play N full games through the real engine and assert zero exceptions and
zero illegal actions. Run with: python tests/test_legality.py [n_games]
"""

import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from cg import game as cg_game  # noqa: E402
from main import agent, read_deck_csv  # noqa: E402

MAX_STEPS_PER_GAME = 4000


def play_one_game(deck0: list[int], deck1: list[int]) -> tuple[int, int]:
    """Returns (result, steps). result: 0/1 winner index, 2 draw."""
    obs, start_data = cg_game.battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(
            f"battle_start failed: errorPlayer={start_data.errorPlayer} errorType={start_data.errorType}"
        )
    steps = 0
    try:
        while obs["current"]["result"] == -1:
            steps += 1
            if steps > MAX_STEPS_PER_GAME:
                raise RuntimeError("game exceeded MAX_STEPS_PER_GAME (possible infinite loop)")
            selection = agent(obs)
            obs = cg_game.battle_select(selection)
        return obs["current"]["result"], steps
    finally:
        cg_game.battle_finish()


def main() -> None:
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    deck = read_deck_csv()

    wins = [0, 0, 0]
    exceptions = 0
    t0 = time.perf_counter()

    for i in range(n_games):
        try:
            result, steps = play_one_game(deck, deck)
            wins[result] += 1
        except Exception as e:
            exceptions += 1
            print(f"[game {i}] EXCEPTION: {type(e).__name__}: {e}")

    elapsed = time.perf_counter() - t0
    print(f"\n{n_games} games in {elapsed:.1f}s ({elapsed / n_games * 1000:.1f} ms/game)")
    print(f"wins: p0={wins[0]} p1={wins[1]} draw={wins[2]}  exceptions={exceptions}")

    assert exceptions == 0, f"{exceptions} game(s) raised an exception (crash or illegal action)"
    print("PASS: zero exceptions, zero illegal actions.")


if __name__ == "__main__":
    main()
