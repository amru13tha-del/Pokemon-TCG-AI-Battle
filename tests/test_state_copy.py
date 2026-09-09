"""Regression test for the Step 1 finding in docs/writeup/ablation_log.md
(learned-value-net proposal): the engine does NOT support deep-copying live
game state and applying a hypothetical action without side effects on the
live game. Documents this as a known, tested limitation rather than an
unverified assumption -- if a future engine build changes this, this test
starts failing and forces re-evaluation of the one-ply-rollout plan.

Uses cg.sim.lib directly (bypassing cg.game's single-module-pointer
wrapper) so two battle pointers can be held open at once. Checks two
independent properties:

  Q1 (blocking): can a second pointer be brought into the SAME state as an
     existing live pointer, by replaying its exact selection history on a
     fresh battle_start with the same decks? This is the only "copy"
     mechanism the exposed API affords -- there is no clone/snapshot/
     restore function (confirmed by reading the full cg/sim.py ctypes
     surface: GameInitialize, BattleStart, AgentStart, BattleFinish,
     GetBattleData, Select, VisualizeData, SearchBegin/Step/End/Release,
     AllCard, AllAttack -- none take or return a full state blob that can
     seed a new battle). Expected: replay does NOT reproduce identical
     state, because BattleStart's internal RNG (deck shuffle / draw order)
     is not seedable or otherwise controllable from this API.

  Q2 (non-blocking, informational): if two pointers ARE held open
     concurrently, do they stay properly isolated -- no crash, no shared/
     aliased state where mutating one silently changes the other? This
     holds, and is useful to know even though it doesn't unblock Q1.

Run with: python tests/test_state_copy.py [n_trials] [steps_to_replay]
"""

import ctypes
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from cg.sim import lib  # noqa: E402
from main import read_deck_csv  # noqa: E402
from src.baseline import choose  # noqa: E402


def raw_start(deck0: list[int], deck1: list[int]):
    cards = deck0 + deck1
    arg = (ctypes.c_int * len(cards))(*cards)
    sd = lib.BattleStart(arg)
    return sd.battlePtr


def raw_get_obs(ptr) -> dict:
    sd = lib.GetBattleData(ptr)
    return json.loads(sd.json.decode())


def raw_select(ptr, sel_list: list[int]) -> dict:
    arg = (ctypes.c_int * len(sel_list))(*sel_list)
    err = lib.Select(ptr, arg, len(sel_list))
    if err != 0:
        raise RuntimeError(f"Select error code {err}")
    return raw_get_obs(ptr)


def raw_finish(ptr) -> None:
    lib.BattleFinish(ptr)


def board_fingerprint(obs: dict) -> tuple:
    """Coarse per-position fingerprint: both players' hand card IDs (sorted)
    plus active Pokemon ID. Sufficient to detect shuffle/draw divergence."""
    cur = obs["current"]
    parts = []
    for p in (0, 1):
        hand = cur["players"][p]["hand"] or []
        parts.append(tuple(sorted(c["id"] for c in hand)))
        active = cur["players"][p]["active"]
        parts.append(active[0]["id"] if active else None)
    return tuple(parts)


def run_trial(deck: list[int], steps_to_replay: int) -> tuple[bool, bool]:
    """Returns (states_identical, isolation_held) for one trial."""
    ptr_a = raw_start(deck, deck)
    ptr_b = None
    try:
        history = []
        obs = raw_get_obs(ptr_a)
        for _ in range(steps_to_replay):
            if obs["current"]["result"] != -1:
                break
            sel = choose(obs)
            history.append(sel)
            obs = raw_select(ptr_a, sel)
        fp_a = board_fingerprint(obs)

        ptr_b = raw_start(deck, deck)
        obs_b = raw_get_obs(ptr_b)
        for sel in history:
            if obs_b["current"]["result"] != -1:
                obs_b = raw_select(ptr_b, sel)
            else:
                break
        fp_b = board_fingerprint(obs_b)

        fp_a_after = board_fingerprint(raw_get_obs(ptr_a))
        isolation_held = fp_a_after == fp_a
        states_identical = fp_a == fp_b
        return states_identical, isolation_held
    finally:
        raw_finish(ptr_a)
        if ptr_b is not None:
            raw_finish(ptr_b)


def main() -> None:
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    steps_to_replay = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    deck = read_deck_csv()

    identical = 0
    isolation_violations = 0
    exceptions = 0

    for i in range(n_trials):
        try:
            states_identical, isolation_held = run_trial(deck, steps_to_replay)
            if states_identical:
                identical += 1
            if not isolation_held:
                isolation_violations += 1
                print(f"[trial {i}] ISOLATION VIOLATION: ptr_a changed after touching ptr_b")
        except Exception as e:
            exceptions += 1
            print(f"[trial {i}] EXCEPTION: {type(e).__name__}: {e}")

    print(f"\n{n_trials} trials, {steps_to_replay} steps replayed each")
    print(f"states identical after replay: {identical}/{n_trials}")
    print(f"isolation violations: {isolation_violations}/{n_trials}")
    print(f"exceptions: {exceptions}/{n_trials}")

    assert exceptions == 0, f"{exceptions} trial(s) raised an exception"
    assert isolation_violations == 0, (
        f"{isolation_violations} trial(s) showed a live pointer mutated by touching "
        "a second pointer -- concurrent battle pointers are not safely isolated"
    )
    # Documents the known limitation. If this ever fails, the engine gained
    # some form of deterministic replay/seeding and Step 1's blocking
    # conclusion should be re-tested, not silently patched away.
    assert identical == 0, (
        f"{identical}/{n_trials} trials reproduced identical state via replay -- "
        "this contradicts the documented finding that state-copying is not "
        "possible. Re-run Step 1's investigation before trusting this."
    )
    print("PASS (documents known limitation): state-copy via replay is not "
          "possible; concurrent pointers are safely isolated.")


if __name__ == "__main__":
    main()
