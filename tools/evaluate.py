"""Evaluate an agent function against an opponent over N games.

Usage: python tools/evaluate.py --games 200 --agent baseline --opponent random
"""

import argparse
import os
import random
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from cg import game as cg_game  # noqa: E402
from main import read_deck_csv  # noqa: E402
from src import baseline  # noqa: E402

MAX_STEPS_PER_GAME = 4000

FALLBACK_COUNT = {"n": 0}


def random_agent(obs_dict: dict) -> list[int]:
    select = obs_dict["select"]
    n_options = len(select["option"])
    return random.sample(range(n_options), select["maxCount"])


def baseline_agent(obs_dict: dict) -> list[int]:
    try:
        return baseline.choose(obs_dict)
    except Exception:
        FALLBACK_COUNT["n"] += 1
        select = obs_dict["select"]
        k = max(select["minCount"], min(select["maxCount"], len(select["option"])))
        return list(range(k))


_bc_model = None


def _get_bc_model():
    global _bc_model
    if _bc_model is None:
        import torch

        from src.qnet import QNet
        m = QNet()
        m.load_state_dict(torch.load(os.path.join(REPO_ROOT, "ckpt", "bc.pt"), map_location="cpu"))
        m.eval()
        _bc_model = m
    return _bc_model


def bc_agent(obs_dict: dict) -> list[int]:
    try:
        import numpy as np
        import torch

        from src import features
        select = obs_dict["select"]
        if select is None:
            return read_deck_csv()
        n_options = len(select["option"])
        state = torch.from_numpy(features.obs_to_state(obs_dict))
        options = torch.from_numpy(
            np.stack([features.option_to_features(obs_dict, i) for i in range(n_options)])
        )
        model = _get_bc_model()
        with torch.no_grad():
            scores = model(state, options)
        k = max(select["minCount"], min(select["maxCount"], n_options))
        return torch.topk(scores, k).indices.tolist()
    except Exception:
        FALLBACK_COUNT["n"] += 1
        select = obs_dict["select"]
        k = max(select["minCount"], min(select["maxCount"], len(select["option"])))
        return list(range(k))


AGENTS = {"random": random_agent, "baseline": baseline_agent, "bc": bc_agent}


def play_one_game(deck0, deck1, agent0, agent1, measured_seat: int, latencies: list[float]) -> int:
    obs, start_data = cg_game.battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(f"battle_start failed: {start_data.errorPlayer} {start_data.errorType}")
    steps = 0
    try:
        while obs["current"]["result"] == -1:
            steps += 1
            if steps > MAX_STEPS_PER_GAME:
                raise RuntimeError("exceeded MAX_STEPS_PER_GAME")
            your_index = obs["current"]["yourIndex"]
            agent_fn = agent0 if your_index == 0 else agent1
            t0 = time.perf_counter()
            selection = agent_fn(obs)
            if your_index == measured_seat:
                latencies.append((time.perf_counter() - t0) * 1000.0)
            obs = cg_game.battle_select(selection)
        return obs["current"]["result"]
    finally:
        cg_game.battle_finish()


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(len(s) * p))
    return s[idx]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--agent", choices=AGENTS.keys(), default="baseline")
    ap.add_argument("--opponent", choices=AGENTS.keys(), default="random")
    args = ap.parse_args()

    agent_fn = AGENTS[args.agent]
    opponent_fn = AGENTS[args.opponent]
    deck = read_deck_csv()

    wins = [0, 0, 0]
    crashes = 0
    latencies: list[float] = []
    t0 = time.perf_counter()

    for i in range(args.games):
        # Alternate seats so neither agent always goes first.
        if i % 2 == 0:
            try:
                result = play_one_game(deck, deck, agent_fn, opponent_fn, 0, latencies)
                wins[result] += 1
            except Exception as e:
                crashes += 1
                print(f"[game {i}] CRASH: {type(e).__name__}: {e}")
        else:
            try:
                result = play_one_game(deck, deck, opponent_fn, agent_fn, 1, latencies)
                wins[1 - result if result in (0, 1) else 2] += 1
            except Exception as e:
                crashes += 1
                print(f"[game {i}] CRASH: {type(e).__name__}: {e}")

    elapsed = time.perf_counter() - t0
    total_decided = wins[0] + wins[1]
    win_rate = wins[0] / args.games if args.games else 0.0

    print(f"\n{args.games} games ({args.agent} vs {args.opponent}) in {elapsed:.1f}s")
    print(f"agent wins={wins[0]} opponent wins={wins[1]} draws={wins[2]} crashes={crashes}")
    print(f"agent win rate: {win_rate * 100:.1f}%")
    print(f"fallback rate: {FALLBACK_COUNT['n']} fallbacks over {len(latencies)} agent decisions")
    if latencies:
        print(f"agent decision latency: p50={percentile(latencies, 0.50):.3f}ms p99={percentile(latencies, 0.99):.3f}ms max={max(latencies):.3f}ms")


if __name__ == "__main__":
    main()
