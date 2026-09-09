"""Regression test for main.agent()'s robustness contract (submission
packaging task): the agent must never raise and every fallback path must
log the exception it caught (to stderr, diagnostic only -- must not change
which action gets returned). Run with: python tests/test_agent_robustness.py
"""

import io
import os
import sys
import contextlib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import main  # noqa: E402
from cg import game as cg_game  # noqa: E402


def _sample_real_obs() -> dict:
    deck = main.read_deck_csv()
    obs, sd = cg_game.battle_start(deck, deck)
    try:
        # advance past deck-selection into a real MAIN decision
        while obs["select"] is None:
            obs = cg_game.battle_select(main.agent(obs))
        return obs
    finally:
        cg_game.battle_finish()


def test_baseline_exception_falls_back_and_logs() -> None:
    obs = _sample_real_obs()
    original = main._baseline_choose
    main._baseline_choose = lambda obs_dict: (_ for _ in ()).throw(RuntimeError("forced failure"))
    try:
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = main.agent(obs)
        assert isinstance(result, list) and all(isinstance(i, int) for i in result), \
            f"agent() did not return a legal-shaped selection: {result!r}"
        logged = buf.getvalue()
        assert "forced failure" in logged, f"exception was not logged to stderr: {logged!r}"
        assert "RuntimeError" in logged
    finally:
        main._baseline_choose = original
    print("PASS: forced src.baseline.choose failure -> random-legal fallback, logged to stderr.")


def test_malformed_obs_falls_back_to_zero_dependency_path() -> None:
    """A obs_dict missing expected keys should still never raise -- must
    reach _legal_fallback, the zero-dependency last resort."""
    malformed = {"select": {"option": [{"type": 14}], "minCount": 1, "maxCount": 1, "context": 0}, "current": None}
    original = main._baseline_choose
    main._baseline_choose = lambda obs_dict: (_ for _ in ()).throw(KeyError("yourIndex"))
    try:
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = main.agent(malformed)
        assert result == [0], f"expected the single legal option [0], got {result!r}"
        logged = buf.getvalue()
        assert "KeyError" in logged or "yourIndex" in logged, f"exception was not logged: {logged!r}"
    finally:
        main._baseline_choose = original
    print("PASS: malformed obs_dict -> still legal, no crash, logged.")


def test_totally_broken_select_falls_back_without_crashing() -> None:
    """select present but missing "option" -- both src.baseline.choose AND
    _random_legal fail on this for real (no mocking), so this exercises
    the genuine, unmocked failure chain all the way to agent()'s outermost
    try/except and _legal_fallback."""
    pathological = {"select": {"minCount": 1, "maxCount": 1, "context": 0}, "current": None}
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result = main.agent(pathological)
    assert isinstance(result, list), f"agent() raised or returned non-list: {result!r}"
    logged = buf.getvalue()
    assert "_policy raised" in logged, f"outer fallback was not logged: {logged!r}"
    print(f"PASS: pathological obs_dict -> {result!r}, no crash, outer fallback logged.")


def main_() -> None:
    test_baseline_exception_falls_back_and_logs()
    test_malformed_obs_falls_back_to_zero_dependency_path()
    test_totally_broken_select_falls_back_without_crashing()
    print("\nALL PASS")


if __name__ == "__main__":
    main_()
