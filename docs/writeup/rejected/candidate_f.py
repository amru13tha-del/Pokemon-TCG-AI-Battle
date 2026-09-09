"""M1 rule-based baseline: hard overrides, a prior score, and a greedy policy.

Interface (deliberately using raw obs_dict, not the cg.api dataclasses --
matches main.py's zero-extra-failure-surface style):

    hard_override(obs_dict)              -> list[int] | None
    baseline_score(obs_dict, option_idx) -> float
    choose(obs_dict)                     -> list[int]

Every rule this module relies on is listed in RULES below with where it was
confirmed. If a rule isn't listed there, this module does not depend on it.
Notably: attack text describes coin-flip / conditional damage bonuses (e.g.
"Flip a coin. If heads, this attack does 20 more damage."), but those
bonuses are only represented as free text and as C++ effect-chain data in
ptcg_engine/ that is not exposed through the runtime API. This module never
tries to parse or estimate them -- it only ever uses Attack.damage, which is
confirmed (see attack_damage_field_is_guaranteed_floor) to already be the
coin-independent floor. That makes every "lethal" call here conservative:
it can miss a lethal that depends on a coin flip, but it will never call a
non-lethal attack lethal.

2026-08-16: a port of ideas from an external reference agent (Mega Lucario ex
archetype) was tried here -- per-turn attack planning, richer target scoring,
role-aware energy attachment, and handling for previously-unscored contexts
(SETUP_ACTIVE_POKEMON, TO_HAND, ATTACH_FROM). It regressed win rate against
this exact prior version (43.3% over 300 games, vs the >55% bar required to
ship) and was reverted. See docs/writeup/mega_lucario_diff.md for the full
comparison and docs/writeup/baseline_pre_port_snapshot.py for the code that
was tested and rejected, kept for the record rather than silently discarded.
"""

from collections import Counter

from cg.api import EnergyType, SelectContext, all_attack, all_card_data

RULES = {
    "engine_filters_legality": (
        "cg/api.py SelectData.option -- the engine only ever offers already-legal "
        "options at a decision point. This module scores/picks among them; it "
        "never re-derives legality."
    ),
    "weakness_doubles_damage": (
        "docs/official/ptcg_engine/SetProperty.h:320-327 -- `damage *= 2` when the "
        "attacking Pokemon's type matches the defender's weakness."
    ),
    "resistance_subtracts_30": (
        "docs/official/ptcg_engine/SetProperty.h:329-338 -- `damage -= 30` (floor 0) "
        "when the attacking Pokemon's type matches the defender's resistance."
    ),
    "attacker_type_is_pokemon_type_not_attack_cost": (
        "docs/official/ptcg_engine/State.h:957-964 (getEnergyType) and "
        "SetProperty.h:270 (`attackerType = state.getEnergyType(attacker)`) -- "
        "weakness/resistance compares the ATTACKING POKEMON's own type "
        "(CardData.energyType), not the attack's energy cost list."
    ),
    "attack_damage_field_is_guaranteed_floor": (
        "Live cg.api.all_attack() sample: 'Comet Punch' (4 coins, 30 dmg/heads) has "
        "damage=0; 'Quick Attack' ('20 more damage if heads') has damage=20; "
        "'Retaliate' ('80 more if a Pokemon was KO'd last turn') has damage=50. "
        "The exposed `damage` field is the coin/condition-independent floor."
    ),
    "prize_value_ex_2_megaex_3": (
        "cg/api.py CardData docstrings: `ex` -> opponent takes 2 prizes on KO, "
        "`megaEx` -> 3 prizes, otherwise 1."
    ),
    "select_type_main_option_kinds": (
        "cg/api.py SelectType.MAIN docstring: 'OptionType: PLAY, ATTACH, EVOLVE, "
        "ABILITY, DISCARD, RETREAT, ATTACK, END'."
    ),
}

_CARD_BY_ID = {c.cardId: c for c in all_card_data()}
_ATTACK_BY_ID = {a.attackId: a for a in all_attack()}


# ---- small observation helpers -------------------------------------------------

def _player(obs_dict: dict, player_index: int) -> dict:
    return obs_dict["current"]["players"][player_index]


def _active(obs_dict: dict, player_index: int) -> dict | None:
    active = _player(obs_dict, player_index)["active"]
    return active[0] if active else None


def _prize_value(card_id: int | None) -> int:
    c = _CARD_BY_ID.get(card_id)
    if c is None:
        return 1
    if c.megaEx:
        return 3
    if c.ex:
        return 2
    return 1


def _can_pay(attached_energies: list[int], cost: list[int]) -> bool:
    """Approximate energy-cost check for a *predicted* (not our own) attack.
    Our own options never need this -- the engine already filters those."""
    attached = Counter(attached_energies)
    cost_c = Counter(cost)
    colorless_needed = cost_c.pop(int(EnergyType.COLORLESS), 0)
    for etype, need in cost_c.items():
        take = min(attached.get(etype, 0), need)
        attached[etype] -= take
        need -= take
        if need > 0:
            take_rainbow = min(attached.get(int(EnergyType.RAINBOW), 0), need)
            attached[int(EnergyType.RAINBOW)] -= take_rainbow
            need -= take_rainbow
        if need > 0:
            return False
    return sum(v for v in attached.values() if v > 0) >= colorless_needed


def _guaranteed_damage(attacker_card_id: int | None, attack_id: int, defender_card_id: int | None) -> int:
    atk = _ATTACK_BY_ID.get(attack_id)
    attacker = _CARD_BY_ID.get(attacker_card_id)
    defender = _CARD_BY_ID.get(defender_card_id)
    if atk is None:
        return 0
    dmg = atk.damage
    if dmg <= 0 or attacker is None or defender is None:
        return max(dmg, 0)
    if defender.weakness is not None and defender.weakness == attacker.energyType:
        dmg *= 2
    if dmg > 0 and defender.resistance is not None and defender.resistance == attacker.energyType:
        dmg = max(0, dmg - 30)
    return dmg


def _max_guaranteed_incoming_damage(attacker_pokemon: dict, attacker_card_id: int, defender_card_id: int) -> int:
    """Best-case (for the attacker) guaranteed damage the attacker could deal to
    defender_card_id next turn, over attacks it can currently pay for."""
    card = _CARD_BY_ID.get(attacker_card_id)
    if card is None:
        return 0
    attached = attacker_pokemon.get("energies") or []
    best = 0
    for attack_id in card.attacks:
        atk = _ATTACK_BY_ID.get(attack_id)
        if atk is None or not _can_pay(attached, atk.energies):
            continue
        best = max(best, _guaranteed_damage(attacker_card_id, attack_id, defender_card_id))
    return best


# ---- hard overrides --------------------------------------------------------------

def _hard_override_main(obs_dict: dict, select: dict, your_index: int) -> int | None:
    opp_index = 1 - your_index
    opp_active = _active(obs_dict, opp_index)
    if opp_active is None:
        return None
    opp_hp_left = opp_active["hp"]
    opp_card_id = opp_active["id"]
    my_prizes_left = len(_player(obs_dict, your_index)["prize"])
    my_active = _active(obs_dict, your_index)
    my_card_id = my_active["id"] if my_active else None
    my_prize_value = _prize_value(my_card_id)

    best_lethal_idx = None
    best_lethal_damage = -1
    best_tradeup_idx = None
    best_tradeup_value = -1

    for i, opt in enumerate(select["option"]):
        if opt.get("type") != 13:  # OptionType.ATTACK
            continue
        attack_id = opt.get("attackId")
        dmg = _guaranteed_damage(my_card_id, attack_id, opp_card_id)
        if dmg <= 0:
            continue
        if dmg >= opp_hp_left:
            # Rule 1: guaranteed KO. Only a game-winner if it also ends the game.
            prize_gain = _prize_value(opp_card_id)
            if prize_gain >= my_prizes_left and dmg > best_lethal_damage:
                best_lethal_idx, best_lethal_damage = i, dmg
            # Rule 2: non-lethal-for-the-game KO that trades their multi-prize
            # Pokemon for my single-prize attacker.
            elif prize_gain >= 2 and my_prize_value == 1 and prize_gain > best_tradeup_value:
                best_tradeup_idx, best_tradeup_value = i, prize_gain

    if best_lethal_idx is not None:
        return best_lethal_idx
    if best_tradeup_idx is not None:
        return best_tradeup_idx
    return None


def _hard_override_switch(obs_dict: dict, select: dict, your_index: int) -> int | None:
    """Rule 3: never voluntarily switch into a Pokemon the opponent can KO for
    free next turn, if a legal alternative exists."""
    opp_index = 1 - your_index
    opp_active = _active(obs_dict, opp_index)
    if opp_active is None:
        return None
    opp_card_id = opp_active["id"]

    safe_candidates = []
    for i, opt in enumerate(select["option"]):
        area = opt.get("area")
        idx = opt.get("index")
        if area != 5 or idx is None:  # AreaType.BENCH
            continue
        bench = _player(obs_dict, your_index)["bench"]
        if idx >= len(bench):
            continue
        candidate = bench[idx]
        incoming = _max_guaranteed_incoming_damage(opp_active, opp_card_id, candidate["id"])
        if incoming < candidate["hp"]:
            safe_candidates.append((i, candidate["hp"] - incoming))

    if not safe_candidates:
        return None  # no safe alternative -- let baseline_score pick
    safe_candidates.sort(key=lambda t: -t[1])
    return safe_candidates[0][0]


def hard_override(obs_dict: dict) -> int | None:
    select = obs_dict.get("select")
    current = obs_dict.get("current")
    if select is None or current is None:
        return None
    your_index = current["yourIndex"]
    context = select["context"]

    if context == int(SelectContext.MAIN):
        return _hard_override_main(obs_dict, select, your_index)
    if context in (int(SelectContext.SWITCH), int(SelectContext.TO_ACTIVE)):
        return _hard_override_switch(obs_dict, select, your_index)
    return None


# ---- prior score (also used to break near-ties and as a fallback) ---------------

def baseline_score(obs_dict: dict, option_idx: int) -> float:
    select = obs_dict["select"]
    current = obs_dict["current"]
    your_index = current["yourIndex"]
    opt = select["option"][option_idx]
    opt_type = opt.get("type")
    context = select["context"]

    if context == int(SelectContext.MAIN):
        opp_index = 1 - your_index
        opp_active = _active(obs_dict, opp_index)

        if opt_type == 13:  # ATTACK
            if opp_active is None:
                return 0.1
            my_active = _active(obs_dict, your_index)
            my_card_id = my_active["id"] if my_active else None
            dmg = _guaranteed_damage(my_card_id, opt.get("attackId"), opp_active["id"])
            score = dmg / 100.0
            if dmg >= opp_active["hp"]:
                score += _prize_value(opp_active["id"])
            return score

        if opt_type == 9:  # EVOLVE
            return 0.6
        if opt_type == 8:  # ATTACH (energy/tool)
            return 0.4
        if opt_type == 10:  # ABILITY
            return 0.3
        if opt_type == 7:  # PLAY (from hand)
            hand = _player(obs_dict, your_index)["hand"] or []
            idx = opt.get("index")
            card_id = hand[idx]["id"] if idx is not None and idx < len(hand) else None
            card = _CARD_BY_ID.get(card_id)
            if card is None:
                return 0.2
            if card.cardType == 3:  # SUPPORTER
                hand_playable = sum(
                    1 for o in select["option"] if o.get("type") in (7, 8, 9, 13)
                )
                return 0.7 if hand_playable <= 2 else 0.5
            if card.cardType == 0:  # POKEMON (bench a basic)
                return 0.45
            return 0.35  # ITEM / TOOL / STADIUM / ENERGY
        if opt_type == 12:  # RETREAT
            if my_active := _active(obs_dict, your_index):
                hp_frac = my_active["hp"] / max(my_active["maxHp"], 1)
                return 0.3 if hp_frac < 0.3 else -0.1
            return -0.1
        if opt_type == 11:  # DISCARD (as a main action, e.g. Item effect start)
            return -0.2
        if opt_type == 14:  # END
            # Candidate F: never let END outscore a legal ATTACK. ATTACK's
            # score floor is exactly 0.0 (guaranteed damage is never
            # negative), so a 0-floor-damage attack (e.g. an all-coin-flip
            # attack whose guaranteed floor is 0) could otherwise tie END
            # and lose on Python's stable sort. Dropping below 0.0 whenever
            # any ATTACK is legal closes that gap unconditionally.
            any_attack_legal = any(o.get("type") == 13 for o in select["option"])
            return -0.05 if any_attack_legal else 0.0
        return 0.1

    if context in (int(SelectContext.SWITCH), int(SelectContext.TO_ACTIVE)):
        area, idx = opt.get("area"), opt.get("index")
        if area == 5 and idx is not None:  # BENCH
            bench = _player(obs_dict, your_index)["bench"]
            if idx < len(bench):
                return bench[idx]["hp"] / max(bench[idx]["maxHp"], 1)
        return 0.0

    if context in (int(SelectContext.EFFECT_TARGET), int(SelectContext.DAMAGE)):
        # Prefer the most valuable, most-nearly-KO'd opposing target (gust logic).
        area, idx = opt.get("area"), opt.get("index")
        if area in (4, 5) and idx is not None:  # ACTIVE or BENCH
            opp_index = 1 - your_index
            pool = _active(obs_dict, opp_index)
            pool = [pool] if area == 4 and pool else _player(obs_dict, opp_index)["bench"]
            if idx < len(pool) and pool[idx]:
                target = pool[idx]
                dmg_taken_frac = 1 - target["hp"] / max(target["maxHp"], 1)
                return _prize_value(target["id"]) + dmg_taken_frac
        return 0.0

    if context == int(SelectContext.DISCARD):
        area, idx = opt.get("area"), opt.get("index")
        if area == 2 and idx is not None:  # HAND
            hand = _player(obs_dict, your_index)["hand"] or []
            if idx < len(hand):
                card = _CARD_BY_ID.get(hand[idx]["id"])
                if card is not None:
                    return 0.5 if card.cardType in (5, 6) else -0.3  # prefer discarding Energy
        return 0.0

    if opt_type == 1:  # YES
        return 0.1
    if opt_type == 2:  # NO
        return 0.0
    return 0.0


# ---- full greedy policy ----------------------------------------------------------

def choose(obs_dict: dict) -> list[int]:
    select = obs_dict["select"]
    n_options = len(select["option"])
    min_count = select["minCount"]
    max_count = select["maxCount"]

    override_idx = hard_override(obs_dict)
    if override_idx is not None:
        base = [override_idx]
    else:
        scored = sorted(range(n_options), key=lambda i: -baseline_score(obs_dict, i))
        base = scored

    k = max(min_count, min(max_count, n_options))
    result = base[:k]
    if len(result) < k:
        result += [i for i in range(n_options) if i not in result][: k - len(result)]
    return result
