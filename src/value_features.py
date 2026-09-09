"""Fixed-length position feature vector for the M1 value net (see
docs/writeup/ablation_log.md, "Learned value-net proposal"). Deliberately
narrow scope per Step 3's spec: prizes remaining both sides, active/bench
HP, energy attached, hand size, deck count. No variable-length action
encoding -- this describes a BOARD POSITION, not a decision's option list.

Also used by Step 2's switch-prediction validator: the same function must
score both a real obs_dict and a hand-constructed hypothetical one
identically, so feature extraction only reads the plain dict shape (no
special-casing "real" vs "predicted" positions).
"""

import numpy as np

FEATURE_DIM = 17  # 7 per-player features (prize, active hp/maxHp/energy,
# bench count/hp_mean/energy_mean) x2 players + hand size + both deck counts
BENCH_MAX = 5  # cg engine's benchMax for this format (confirmed empirically)
HAND_CAP = 10.0
HP_CAP = 250.0  # generous upper bound; no card in the current card pool exceeds this


def _pokemon_hp_frac(pokemon: dict | None) -> float:
    if not pokemon:
        return 0.0
    return pokemon["hp"] / max(pokemon["maxHp"], 1)


def _pokemon_energy_count(pokemon: dict | None) -> float:
    if not pokemon:
        return 0.0
    return min(len(pokemon.get("energies") or []), 6) / 6.0


def _player_features(player: dict) -> list[float]:
    active = player["active"][0] if player["active"] else None
    bench = player["bench"] or []
    bench_hp_fracs = [_pokemon_hp_frac(b) for b in bench]
    bench_energy = [_pokemon_energy_count(b) for b in bench]
    return [
        len(player["prize"] or []) / 6.0,
        _pokemon_hp_frac(active),
        (active["maxHp"] / HP_CAP) if active else 0.0,
        _pokemon_energy_count(active),
        min(len(bench), BENCH_MAX) / BENCH_MAX,
        (sum(bench_hp_fracs) / len(bench_hp_fracs)) if bench_hp_fracs else 0.0,
        (sum(bench_energy) / len(bench_energy)) if bench_energy else 0.0,
    ]


def position_features(obs_dict: dict, player_index: int) -> np.ndarray:
    """Feature vector from `player_index`'s perspective -- this player is
    assumed to be the player to move (value net predicts their win prob)."""
    players = obs_dict["current"]["players"]
    me = players[player_index]
    opp = players[1 - player_index]
    v = _player_features(me) + _player_features(opp)
    v.append(min(me["handCount"], HAND_CAP) / HAND_CAP)
    v.append(min(me["deckCount"], 60) / 60.0)
    v.append(min(opp["deckCount"], 60) / 60.0)
    arr = np.asarray(v, dtype=np.float32)
    assert arr.shape == (FEATURE_DIM,), f"expected {FEATURE_DIM} features, got {arr.shape}"
    return arr
