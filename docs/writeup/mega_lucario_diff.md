# Diff: `docs/writeup/mega_lucario_reference.py` vs `src/baseline.py`

Reference file line numbers below refer to the copy saved at
`docs/writeup/mega_lucario_reference.py`. Our line numbers refer to
`src/baseline.py` as of 2026-08-16, before this port.

**Caveat on the 664 vs 406 scores:** unverified by us. We have the code, not an
independent confirmation of its leaderboard result. The only score that matters
for the go/no-go decision here is our own 300-game local test (see report below).

## 1. AttackPlan (reference lines ~44-49, ~185-270) — REAL GAP, PORTED

Reference commits to `(attacker, attack, target)` once per turn (reset on
`pre_turn != state.turn`, ref lines ~157-161) inside the MAIN-select scoring
block, then every later decision in that turn (SWITCH/TO_ACTIVE, ATTACH,
RETREAT, ATTACK option scoring) reads `plan.attacker`/`plan.target`/`plan.energy`
to stay consistent with it (e.g. ref line ~333: energy attach gets +200 if it's
going to `plan.attacker`; ref line ~372: RETREAT only scores positive if
`plan.attacker >= 1`).

Our `baseline_score()` (`src/baseline.py:229-319`) scores every decision
independently, with no persistent state connecting them. In practice this means
we could, in principle, attach energy to one Pokemon while ending up attacking
with another, or retreat away from a Pokemon we'd just invested energy in — nothing
enforces turn-level coherence.

**Ported, adapted for our deck.** One real difference worth flagging: the
reference assumes it only ever pilots one seat (a real ladder submission is one
process per side). We call `baseline.choose()` for **both** seats in self-play
(`main.py`'s own smoke test, `tools/self_play_log.py`, `tools/evaluate.py`,
`src/train_dqn.py`'s `baseline_policy_act`), so a single module-level `plan`
would leak between player 0's and player 1's decisions when both use baseline in
the same game. Keyed the plan state by player index to avoid that — not a
consideration the reference needed to make, since it was written for actual
submission use.

## 2. `prize_count()` card modifiers (reference lines ~90-98) — REAL GAP, NOT PORTED

We already have the base 3/2/1 rule (`src/baseline.py:78-86`, `_prize_value()`,
cites `prize_value_ex_2_megaex_3` in `RULES`). The reference additionally
subtracts 1 prize for "Legacy Energy" (id 12) attached or "Lillie's Pearl"
(id 1172) on a Pokemon named "Lillie". Real modifier, but tied to specific cards
neither our deck nor (as far as we've observed) our opponents run. **Not
ported** — would be speculative tuning for a matchup we have no evidence we'll
see. Worth adding if we ever build a broader opponent test suite (a gap already
flagged in `docs/writeup/outline.md`).

## 3. `pokemon_score()` target weighting (reference lines ~101-116) — REAL GAP, PORTED (partially)

Our target-selection scoring (`src/baseline.py:292-303`, used for
`EFFECT_TARGET`/`DAMAGE` contexts) is `prize_value + damage_taken_fraction` only.
Reference weights by `prize_count*1000 + energy_count*150 + tools*100 +
stage_bonus + hp`, plus specific opponent-card-ID adjustments (a few named
Pokemon get +/- 200-300).

**Ported the general formula** (prize value, attached energy, tools, evolution
stage, HP) since it's a legitimate improvement independent of any specific
meta. **Did not port the named-card special cases** (Noctowl/Fan Rotom/
Archaludon ex/Meowth ex/Munkidori) — those are tuned to threats we have no
evidence about, and porting card-ID-specific adjustments without knowing why
they were chosen is exactly the kind of "situational advantage" the Strategy
track's own rubric warns against relying on.

## 4. Weakness ×2 / resistance −30 before KO check — ALREADY HAVE, NO GAP

Reference: `data.weakness == EnergyType.FIGHTING: damage *= 2` / `elif
data.resistance ==...: damage -= 30` (hardcoded to Fighting since that's their
attacker's only type). We already do this generically in
`_guaranteed_damage()` (`src/baseline.py:108-121`), keyed off the *attacking
Pokemon's actual type* rather than hardcoded, and separately `if`-gated (not
`elif`) matching the real engine structure we read directly from
`SetProperty.h:320-338` — the reference's `elif` is functionally equivalent in
every real case (a card can't be weak and resistant to the same type) but ours
is closer to the actual engine logic. **No change needed; we're already at
least as correct.**

## 5. Instant-win override ("score it 50000") — ALREADY HAVE, reference version looks buggy

Reference (line ~230): `if len(op_state.prize) <= prize: score = 50000` — checks
the **opponent's** remaining prize count against the prize value this KO would
award **us**. That's checking the wrong player's prize pile: a KO wins the game
when it brings *our own* remaining prizes to zero, not the opponent's (each
player has their own separate prize pile in this engine, confirmed via
`cg/api.py`'s `PlayerState.prize` docstring and our own tested play). Our
`_hard_override_main()` (`src/baseline.py:166-174`) checks
`prize_gain >= my_prizes_left`, i.e. the correct player's count, and this has
been battle-tested across our M0/M1 evaluation runs and ladder submissions.
**Not porting the reference's version — flagging it as a likely bug rather than
silently fixing someone else's code without being asked to.** Our existing
implementation is kept as-is.

## 6. Energy attachment scored per-role (reference `energy_score()`, lines ~215-231) — REAL GAP, PORTED

Our current scoring gives a flat `0.4` to *any* `ATTACH`-type option
(`src/baseline.py:254-255`) regardless of which Pokemon receives it, and has
**no handling at all** for `SelectContext.ATTACH_FROM` (the follow-up
card-selection step where you actually pick *which* Pokemon an energy/tool goes
to) — that context falls through to the generic `return 0.0` default
(`src/baseline.py:319`), so ties get broken by Python's stable sort and we
always pick whichever Pokemon happened to be listed first. Reference scores by
role: prioritizes under-fueled attackers, deprioritizes over-investing in an
already-ready attacker when another of the same role exists, and boosts the
active Pokemon.

**Ported and adapted**: our deck has three attacker roles (Throh needs 2
energy for Shoulder Throw, Landorus needs 3 for Screw Knuckle, Terrakion needs
3), so the port scores by "how close is this Pokemon to affording its attack"
rather than the reference's Mega-Lucario-specific role names, and adds real
handling for `ATTACH_FROM` (previously entirely unhandled).

## Additional gaps found scanning the rest of the reference (not in your list)

- **`SelectContext.SETUP_ACTIVE_POKEMON`** (ref lines ~296-303): reference
  explicitly reasons about which Basic to lead with. We have **zero** handling
  for this context — falls to the `0.0` default, so we always lead with
  whichever Basic is listed first, with no strategic input. **Ported**: prefer
  leading with whichever of our three attackers is closest to affording its
  attack, matching how we already score other decisions.
- **`SelectContext.TO_HAND`** (ref lines ~304-330): reference scores which
  card to fetch when searching/revealing (avoids over-fetching a redundant
  copy already in play). We have **zero** handling — falls to `0.0` again.
  This is directly relevant to us: Ultra Ball, Poké Pad, Fighting Gong, and
  Boxed Order are all in our deck and can trigger this exact context.
  **Ported**: prefer fetching a Basic attacker if none is in play yet, else
  prefer Fighting Energy if short on it, else prefer a Supporter/search Item.
- **Stadium awareness for `Gravity_Mountain`** (ref line ~460): don't replay a
  Stadium if one's already active. We run Lively Stadium; **not ported** —
  replaying an identical copy of our own Stadium is a no-op in this engine, so
  there's no actual downside to guard against for our specific deck (unlike
  the reference, which runs a Stadium that presumably matters more contextually).
- **`ability_used` turn-tracking** (ref, tied to Lunatone's ability): **not
  applicable** — none of Throh/Landorus/Terrakion have abilities
  (confirmed empty `skills` list for all three when we surveyed the card pool
  while building the deck).
- **Boss Orders / gust-target planning** (ref line ~430): **not applicable** —
  our deck has no forced-switch effect on the opponent's side.
