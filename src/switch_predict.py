"""Step 2 of the value-net proposal (docs/writeup/ablation_log.md): predict
the resulting position of a SWITCH (voluntary retreat, or the "Switch"
trainer card) decision WITHOUT calling the engine, since true
state-copy/rollback isn't available (Step 1 finding). This only works for
SWITCH because it's a pure, deterministic relabeling given full information
already visible in the current obs_dict -- no hidden information, no RNG,
no coin flips, unlike attacks or draws.

Real rules encoded here (confirmed against a live traced retreat sequence
AND corrected against tests/test_switch_prediction.py's ground-truth
validation -- the first version double-subtracted retreat cost, see below):
  1. Retreat cost is NOT deducted here. By the time a SWITCH-context
     decision is presented, the engine has already resolved cost payment
     as a separate, earlier decision (RETREAT -> an ENERGY-discard
     decision -> THEN this SWITCH decision) -- the active's `energies` in
     the incoming obs_dict already reflects that. The "Switch" trainer card
     (id 1123 in this deck) reaches the same SWITCH context with no cost at
     all. Both cases are already fully resolved by the time we see this
     obs_dict; subtracting cost again here was a real bug, caught by the
     validation test (792/1107 SWITCH decisions mismatched on the first
     version, isolated to the bench-energy feature specifically).
  2. All special conditions clear on retreat (poisoned/burned/asleep/
     paralyzed/confused all reset to False) -- the new active came from the
     bench, where conditions can't exist, and the retreating Pokemon loses
     its conditions per the real TCG rules.
  3. HP, maxHp, energies, tools, and preEvolution are otherwise unchanged
     for both the promoted and the demoted Pokemon.
  4. Bench composition changes (target removed, old active added) but exact
     positional ordering within bench is NOT reproduced here -- validated
     instead via order-invariant aggregate features (src/value_features.py),
     not a byte-for-byte dict diff. The real engine's bench slot ordering
     convention isn't part of what the value net needs to know.
"""

import copy


def predict_post_switch(obs_dict: dict, player_index: int, bench_target_idx: int) -> dict:
    """Returns a deep-copied obs_dict, mutated to reflect the predicted
    result of switching the current active with bench_target_idx. Only
    touches `player_index`'s active/bench/status fields -- everything else
    (opponent's board, hand, deck counts, prizes) is untouched by a switch."""
    predicted = copy.deepcopy(obs_dict)
    player = predicted["current"]["players"][player_index]
    active = player["active"][0] if player["active"] else None
    bench = player["bench"] or []
    if active is None or bench_target_idx >= len(bench):
        return predicted  # nothing sensible to predict; caller's problem

    target = bench.pop(bench_target_idx)
    bench.append(active)
    player["active"] = [target]
    player["bench"] = bench

    for status in ("poisoned", "burned", "asleep", "paralyzed", "confused"):
        if status in player:
            player[status] = False

    return predicted
