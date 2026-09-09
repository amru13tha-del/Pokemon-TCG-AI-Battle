# Ablation log — src/baseline.py single-change protocol

Started 2026-08-16, after the bundled Mega Lucario port regressed to 43.3% win
rate against the actual prior baseline (see `mega_lucario_diff.md` and the
`ptcg-mega-lucario-episode` memory). This log tracks one change at a time
against a frozen control, per the protocol below.

## Methodology notes / deviations from the requested protocol

- **Seed-freezing is not achievable and was not attempted.** Checked the full
  ctypes binding surface in `cg/sim.py`: `BattleStart` takes only the combined
  deck card list, no seed parameter exists anywhere in the exposed API.
  Confirmed empirically too -- ran the identical policy against itself twice
  (10 games each, same code, same deck): results differed both times (win/loss
  pattern and step counts both varied). The engine's internal RNG isn't
  controllable from our Python bindings. No `tests/seeds.json` was created --
  a file claiming to freeze reproducibility without an actual seed mechanism
  behind it would be a fake artifact. **Substitute: N=300 games per
  comparison, alternating which side goes first each game** (same pattern
  `tools/evaluate.py` already uses), relying on sample size rather than
  matched seeds for comparability across cycles.
- **Control file**: `docs/writeup/baseline_control.py`, a byte-for-byte copy
  of `src/baseline.py` taken before any candidate in this log was implemented.
  `src/baseline.py` is never edited without this copy existing first.
- **Candidate B (KO-first attack selection, weakness/resistance before
  comparison) is already implemented** in the control -- `_guaranteed_damage()`
  applies weakness/resistance before any KO comparison, used by both
  `_hard_override_main`'s lethal/trade-up rules and `baseline_score`'s ATTACK
  branch. Logged as "already satisfied," not ported.

## Acceptance gate (per instruction)

Accept a candidate only if: win rate vs `baseline_control.py` >= 53% **and**
crashes == 0. No tuning to rescue a failing candidate -- reject and move on.

**Amendment (2026-08-17, user-requested):** any candidate that clears the
53%/300-game bar must be re-confirmed at 1000 games before final acceptance
-- 300 games has ~2.9% standard error, and 53% alone is within noise of a
true 50%. As with the original 300-game protocol, the engine has no seed
control (see above), so "fresh seed list" is substituted with 1000 fresh
alternating-seat games rather than a matched seed set. A candidate that
passes 300 but fails the 1000-game confirmation is rejected, logged as
"passed 300, failed 1000-game confirmation," and treated the same as any
other rejection.

---

## Candidate A: SETUP_ACTIVE_POKEMON / TO_HAND / ATTACH_FROM handling

**Hypothesis:** these three contexts fall through to the generic `0.0` default
today, so ties break by Python's stable sort (whichever option is listed
first wins, with zero strategic input). Adding real scoring should be a pure
correctness fix with little downside.

**Implementation:** SETUP_ACTIVE_POKEMON scores by cheapest-attack-cost among
the Basic being considered; TO_HAND prefers a Basic if none is in play yet,
else Energy > Supporter > other, restricted to `area == DECK` (the only
source our deck's search cards -- Ultra Ball, Poke Pad, Fighting Gong, Boxed
Order -- ever trigger); ATTACH_FROM gets a flat 0.4 (matches MAIN-select
ATTACH's existing default) since no card in our deck exercises this context
at all. Deliberately did not reference the per-turn plan mechanism from the
Mega Lucario port -- that's a separate, unrequested change and bundling it in
would violate the one-change-per-cycle rule.

**Result (300 games each):**

| Comparison | Win rate | Crashes | Fallbacks | Mean latency | p95 latency |
|---|---|---|---|---|---|
| vs M0 random | 87.0% (261/300) | 0 | 0 | 0.071ms | 0.178ms |
| vs `baseline_control.py` | **45.7%** (137/300) | 0 | 0 | 0.065ms | 0.170ms |

**Verdict: REJECT.** 45.7% < the 53% bar. Note: at n=300 the standard error
around a true 50% is ~2.9%, so this specific number is only ~1.5 SE below
even-money -- plausibly noise rather than a real regression, especially given
SETUP_ACTIVE_POKEMON is very likely a no-op for this deck specifically (all
three attackers -- Throh, Landorus, Terrakion -- have an identical
cheapest-attack cost of 2 energy, so the new scoring never actually breaks
their tie) and ATTACH_FROM never triggers at all. But the gate is mechanical
and absolute per instruction, not "distinguishable from 50%" -- reject as
measured, no rescue tuning, move on. Rejected diff:
`docs/writeup/rejected/candidate_a.py`. `src/baseline.py` reverted to
`baseline_control.py` (hash-verified identical).

**Instrumentation added retroactively (2026-08-17), per user request.** Ran
300 control (`baseline_control.py` self-play) games and counted how often
each of Candidate A's three target contexts actually appears in the legal-
decision stream, across 48,843 total decisions:

| Context | Count | % of decisions | Games with >=1 occurrence |
|---|---|---|---|
| SETUP_ACTIVE_POKEMON | 600 | 1.23% | 300 / 300 (exactly 2/game) |
| TO_HAND | 6,697 | 13.71% | 300 / 300 (~22/game) |
| ATTACH_FROM | 0 | 0.00% | 0 / 300 |

This does **not** uniformly support "Candidate A was underpowered rather
than disproven" -- the three contexts split into three different stories:
- **ATTACH_FROM**: confirmed dead code for this deck, 0 occurrences in
  48,843 decisions. This part of Candidate A never influenced a single game
  either way -- not underpowered, simply irrelevant here.
- **SETUP_ACTIVE_POKEMON**: fires in every game (exactly twice, once per
  player), so it isn't rare -- but it's a *structural* no-op regardless of
  sample size, because all three deck attackers tie at the same 2-energy
  minimum attack cost that the new scoring logic keys on. More games
  wouldn't change this; the tie is by construction, not by chance.
- **TO_HAND**: genuinely frequent -- 13.71% of all decisions, present in
  every game, ~22 times per game. This context had real statistical
  exposure in the 300-game test. If Candidate A's TO_HAND scoring logic was
  actually worse than the control's default fallthrough, the test had ample
  power to detect that -- this is the one piece of Candidate A's regression
  that should be read as a plausible real effect, not a sampling artifact.

Net: the honest revision to the original hedge is that Candidate A's 45.7%
result is more likely attributable to TO_HAND specifically (frequent,
exercised, plausible real regression) than to noise diluted across three
contexts of which two are rare. ATTACH_FROM is exonerated by construction
(never ran). SETUP_ACTIVE_POKEMON is exonerated by the cost-tie (ran often,
provably inert). Re-testing a TO_HAND-only change in isolation would be the
correct follow-up if this is ever revisited, per the one-change-per-cycle
rule -- not attempted here, out of scope for this retroactive note.

## Candidate B: KO-first attack selection with weakness/resistance

**Status: already implemented in the control, not a gap.** `_guaranteed_damage()`
applies weakness (x2) and resistance (-30) before any KO comparison; both
`_hard_override_main`'s lethal/trade-up rules and `baseline_score`'s ATTACK
branch already gate on `dmg >= opp_active["hp"]` using that pre-adjusted
value. No change made, no evaluation run -- there was nothing to test.

---

## Candidate C: role-aware energy attachment

**Hypothesis:** ATTACH options score a flat 0.4 regardless of which Pokemon
they target, so ties between "attach to active" and "attach to a bench
Pokemon" break on whatever order the engine lists them in, not on which
target actually benefits. Scoring energy ATTACH options by whether the
attachment unlocks (or keeps unlocked) a payable attack on the target should
route energy to whichever Pokemon can use it soonest.

**Implementation:** added `_energy_readiness(target, provided_energy_type)`,
comparing `_can_pay()` on the target's attacks before vs. after adding one
energy of the type being attached. In `baseline_score`'s ATTACH branch
(restricted to `cardType in (5, 6)`, i.e. Basic/Special Energy only --
Tool-card ATTACH options are untouched): unlocking a previously-unpayable
attack scores 0.5 (up from 0.4); an attachment that still leaves every attack
unpayable afterward scores 0.3 (down from 0.4); an already-ready target
(payable before and after) keeps the default 0.4.

**Result (300 games each):**

| Comparison | Win rate | Crashes | Fallbacks | Mean latency | p95 latency |
|---|---|---|---|---|---|
| vs M0 random | 78.3% (235/300) | 0 | 0 | 0.503ms | 1.993ms |
| vs `baseline_control.py` | **31.3%** (94/300) | 0 | 0 | 0.230ms | 0.941ms |

**Verdict: REJECT.** 31.3% is a real regression, not noise -- at n=300 the
standard error around 50% is ~2.9%, so this result is roughly 6 SE below
even money (contrast Candidate A's 45.7%, which was only ~1.5 SE out and
plausibly noise). Root cause, confirmed by reading the interacting code
rather than just asserting it: every attacker in this deck (Throh, Landorus,
Terrakion) needs >=2 energy for its cheapest attack, so the *first* energy
attached to any Pokemon this game always falls into the new "still not
payable after" branch and scores 0.3. That is now *below* `PLAY` for an Item
card (0.35, unchanged, `baseline_score` MAIN branch), whereas under the
control ATTACH's flat 0.4 always outranked item plays. This flips action
order within a turn: search/draw items (e.g. Ultra Ball, which discards 2
cards from hand as its cost) now get played *before* that turn's energy
attach whenever both are legal in the same decision. The pre-existing
DISCARD-context scoring (`baseline_score`, HAND branch, line ~354) already
prefers discarding Energy cards over other types -- a rule that was harmless
under the control because energy always got attached first, but under
Candidate C it now regularly discards the very energy card that would have
been attached, as part of an item's cost. This is a genuine, mechanistically-
explained regression, not a fluke. Per protocol, not patching the DISCARD
interaction to rescue this candidate -- that would be a second, unrequested
change smuggled in to save a failing one. Rejected diff:
`docs/writeup/rejected/candidate_c.py`. `src/baseline.py` reverted to
`baseline_control.py` (hash-verified identical,
`8DD8833B0C1D19DD616B2D145AD0AE0242DB52CB03B12D26E14FCFC7AC4E99F3`).

**Follow-up note for later candidates:** this exposed a latent, pre-existing
issue worth a future single-change cycle of its own -- the DISCARD-context
"prefer discarding Energy" rule doesn't check whether the energy being
discarded is spare (already attached elsewhere / a duplicate in hand with
more copies available) versus the only copy on the way to being attached
this turn. Not in scope for Candidate C and not fixed here; flagging it so it
isn't lost.

---

## Candidate D: retreat gating

**Hypothesis:** the control's RETREAT score is a crude HP threshold (`0.3` if
active HP < 30%, else `-0.1`) with no regard for whether retreating actually
helps -- it doesn't check if the active could just attack instead, whether
any benched Pokemon is ready to fight if promoted, or whether the retreat
cost would fully drain the active's own energy investment. Gating on all
three, per the candidate spec, should cut wasted/harmful retreats.

**Implementation:** added `_retreat_justified()`, replacing the HP-threshold
check entirely (one idea per cycle -- did not keep the old HP logic
alongside the new gate). Returns `False` (blocking a good score) if: (1) the
active can already pay for and profitably use one of its own attacks this
turn, or (2) no benched Pokemon can currently pay for any of its own attacks
if promoted, or (3) paying the retreat cost would leave the active (now
benched) with 0 energy after having attached at least 1 (stranding that
investment). `baseline_score`'s RETREAT branch returns `0.5` when justified,
`-0.3` otherwise (both engine-guaranteed-legal retreat cost payability is
unchanged -- the engine already filters that).

**Result (300 games each):**

| Comparison | Win rate | Crashes | Fallbacks | Mean latency | p95 latency |
|---|---|---|---|---|---|
| vs M0 random | 92.3% (277/300) | 0 | 0 | 0.057ms | 0.151ms |
| vs `baseline_control.py` | **52.3%** (157/300) | 0 | 0 | 0.041ms | 0.113ms |

**Verdict: REJECT.** 52.3% < the 53% bar -- close (only 0.7 points short,
well within the ~2.9% standard error at n=300, so this is essentially a coin
flip and plausibly would land on either side of the bar on a re-run) but the
gate is mechanical and absolute per instruction, not "close enough." No
rescue tuning. Rejected diff: `docs/writeup/rejected/candidate_d.py`.
`src/baseline.py` reverted to `baseline_control.py` (hash-verified identical,
`8DD8833B0C1D19DD616B2D145AD0AE0242DB52CB03B12D26E14FCFC7AC4E99F3`).

---

## Candidate E: supporter ordering

**Hypothesis:** the control scores a Supporter play at 0.7 (or 0.5 if
hand_playable > 2), which is often *lower* than a good ATTACK's score
(`dmg / 100 + prize_value_on_KO`, e.g. any attack over 70 damage already
beats 0.7). Since attacking ends the turn, a draw/search supporter that
scores below the attack never gets played that turn -- its value is
foregone entirely, and any downstream MAIN decision never sees the drawn
cards. Deck's only Supporter is Cheren ("Draw 3 cards.", no discard cost --
checked via `all_card_data()` before implementing, specifically to rule out
a Candidate-C-style collateral-discard interaction).

**Implementation:** replaced the conditional 0.7/0.5 scoring with an
unconditional `9.0` for any `PLAY` of a `cardType == 3` (SUPPORTER) card --
safely above any plausible ATTACK score in this game (bounded well under
9.0) and above EVOLVE/ATTACH/ABILITY, so a legal supporter play always
resolves before attach/attack/evolve within the same turn. Hard-override
lethal/trade-up checks (`_hard_override_main`) run before `baseline_score`
is ever consulted, so this cannot cause a missed game-winning attack --
verified this reasoning against the code, not just assumed it.

**Result (300 games each):**

| Comparison | Win rate | Crashes | Fallbacks | Mean latency | p95 latency |
|---|---|---|---|---|---|
| vs M0 random | 89.7% (269/300) | 0 | 0 | 0.051ms | 0.133ms |
| vs `baseline_control.py` | **49.3%** (148/300) | 0 | 0 | 0.039ms | 0.107ms |

**Verdict: REJECT.** 49.3% is a coin flip (~0.24 SE below 50% at n=300) --
essentially zero measurable signal either direction. With only one Supporter
in the deck, drawn near-uniformly throughout the game, always-first
ordering apparently doesn't matter much: Cheren has no discard cost, so
there's no downside window it could avoid, and playing it slightly later in
the same turn (whenever the old 0.5/0.7 logic already ranked it above
ATTACH/ABILITY/EVOLVE, which is most of the time) already captured most of
the value. No crashes, no fallbacks. Rejected diff:
`docs/writeup/rejected/candidate_e.py`. `src/baseline.py` reverted to
`baseline_control.py` (hash-verified identical,
`8DD8833B0C1D19DD616B2D145AD0AE0242DB52CB03B12D26E14FCFC7AC4E99F3`).

---

## Candidate F: never pass up a legal attack in favour of END

**Hypothesis:** the control scores END at a flat `0.0`, the same floor as
ATTACK's score (`_guaranteed_damage` never returns negative, so an attack
whose guaranteed-floor damage is exactly 0 -- e.g. an all-coin-flip attack --
would score `0.0` too). A tie between END and a 0-floor ATTACK is broken by
Python's stable sort on `select["option"]` order, meaning the agent could
end its turn instead of throwing an attack that has real (coin-dependent)
expected damage, purely because of list order. Note: a literal runtime
`assert` inside `choose()`/`baseline_score()` was deliberately **not** used
to enforce this -- that would turn a would-be violation into an actual crash
during real play, directly violating the zero-crash gate. The fix is a
scoring change (a guarantee by construction, not a live check), plus a
separate regression test that verifies the invariant empirically.

**Implementation:** `baseline_score`'s END branch now returns `-0.05`
whenever any ATTACK option is present in the same decision (`0.0` otherwise,
unchanged). Since ATTACK's score floor is `0.0`, this makes END strictly
worse than *any* legal attack, unconditionally. New file
`tests/test_no_pass_on_attack.py` (run as a script, matching
`tests/test_legality.py`'s convention, not pytest) plays N games and asserts
`choose()` never returns an END option in the same decision where an ATTACK
option was legal.

**Pre-implementation check:** before evaluating, checked whether this bug
can even occur with the current deck. All 6 attacks across Throh, Landorus,
and Terrakion have guaranteed-floor damage of 50-120 (`all_attack()`), none
at 0. That means every legal ATTACK for this deck already scores >= 0.5,
comfortably above END's *old* 0.0 -- so the tie this fix closes is
mathematically unreachable with this specific card pool. Confirmed
empirically too: ran the new test's violation-detection logic against the
unfixed control for 300 games -- 0 violations. **This candidate is a
provable structural no-op for the current deck**, not a hypothesis that
happened to fail.

**Result (300 games each):**

| Comparison | Win rate | Crashes | Fallbacks | Mean latency | p95 latency |
|---|---|---|---|---|---|
| vs M0 random | 88.0% (264/300) | 0 | 0 | 0.044ms | 0.110ms |
| vs `baseline_control.py` | 50.7% (152/300) | 0 | 0 | 0.029ms | 0.075ms |

**Verdict: REJECT (scoring change), KEEP (regression test).** 50.7% is
exactly what a no-op should measure -- pure engine-RNG noise around 50%,
confirming the equivalence proof above rather than contradicting it. The
53%-win-rate gate cannot distinguish "no behavioral difference" from "no
improvement," and per protocol a candidate that doesn't clear the bar is
rejected regardless of why -- no exception carved out here, applying the
same mechanical standard as every other candidate in this log. Reverted the
`baseline_score` change; `src/baseline.py` is hash-verified identical to
`baseline_control.py` again (`8DD8833B0C1D19DD616B2D145AD0AE0242DB52CB03B12D26E14FCFC7AC4E99F3`).
Rejected diff: `docs/writeup/rejected/candidate_f.py`.

`tests/test_no_pass_on_attack.py` is **kept** despite the score change being
reverted -- it was explicitly requested as its own deliverable ("add a
regression test for this specifically"), it passes cleanly against the
reverted control (0 violations / 30 games, matching the 300-game check
above), and it protects against a real future risk that today's deck
happens not to expose: any future accepted candidate, or any future deck
that includes a coin-flip/conditional-only attacker (0 guaranteed-floor
damage), reintroducing exactly this gap. Keeping a free, currently-inert
safety net is not the same as rescue-tuning a failing candidate -- the src
change it was testing was still rejected on the numbers, unmodified.

---

## Final summary

| Candidate | Idea | Verdict | Win rate vs control (n=300) |
|---|---|---|---|
| A | SETUP_ACTIVE_POKEMON / TO_HAND / ATTACH_FROM handling | REJECT | 45.7% |
| B | KO-first attack selection w/ weakness/resistance | Already satisfied in control | n/a |
| C | Role-aware energy attachment | REJECT (real regression, root-caused) | 31.3% |
| D | Retreat gating | REJECT | 52.3% |
| E | Supporter ordering | REJECT | 49.3% |
| F | Never pass a legal attack for END | REJECT (proven no-op), test kept | 50.7% |

**Zero of the six candidates were accepted.** `src/baseline.py` is
byte-identical to `docs/writeup/baseline_control.py`
(`8DD8833B0C1D19DD616B2D145AD0AE0242DB52CB03B12D26E14FCFC7AC4E99F3`) at the
end of this protocol -- the only durable code change to ship out of this
entire cycle is `tests/test_no_pass_on_attack.py`, a new regression test
that adds coverage without changing behavior. Per the deliverable's stacking
requirement ("re-run the full 300-game evaluation on the stacked version"):
since nothing was accepted, there is no stack to re-evaluate -- the
stacked-version number is definitionally identical to the standalone control
numbers already reported for each candidate above (a fresh 300-game
control-vs-control run would only remeasure engine noise, not a real
comparison). Not run, for that reason, rather than silently skipped.

This is a clean, useful result for the Strategy Writeup's "hypotheses
tested" section: six concrete, independently-motivated ideas, each isolated
and evaluated on identical footing against a frozen control, with one
real regression fully root-caused (Candidate C's DISCARD interaction) rather
than left as an unexplained number. The control baseline turns out to
already be a reasonably strong local optimum for this specific deck and
action-scoring structure.

---

## Learned value-net proposal -- Step 1: state-copy verification

**Goal (2026-08-27):** since single-change ablation exhausted the local
optimum around M1's hand-written scoring, next proposal is a learned
position evaluator M1 consults via one-ply rollout (`(1-w)*heuristic +
w*value_net`), not a replacement for M1's decision logic. Step 1 of that
plan, run before any of the rest: confirm the engine allows deep-copying
live game state and applying a hypothetical action without side effects on
the live game -- this is a hard prerequisite for Step 2's one-ply rollout
(evaluate the resulting position of each legal action from the *actual
current* game state).

**Investigation:** read the complete `cg/sim.py` ctypes binding surface
again (`GameInitialize`, `BattleStart`, `AgentStart`, `BattleFinish`,
`GetBattleData`, `Select`, `VisualizeData`, `SearchBegin/Step/End/Release`,
`AllCard`, `AllAttack`) and grepped the whole repo for
clone/snapshot/deepcopy/fork/load-state/save-state/restore -- no such
function exists anywhere in the exposed API or anywhere else in the repo.
`BattleStart` only accepts two 60-card deck lists (fresh game), never an
existing state blob. `GetBattleData`'s `data`/`count` fields are ASCII
search-UI payload (`search_begin_input`), not a full serialized state, and
there is no corresponding load/restore call for them regardless.

The only theoretically available "copy" mechanism given that: start a
second, independent battle pointer with the same two decks, and replay the
exact sequence of selections that produced the live pointer's current
state, hoping the fresh pointer lands in the same position. `cg/game.py`
tracks only one pointer at module scope (`Battle.battle_ptr`), so this
requires calling `cg.sim.lib` directly with explicit pointers, bypassing
that wrapper -- confirmed doable (`lib.BattleStart`/`lib.Select`/
`lib.GetBattleData`/`lib.BattleFinish` all take an explicit `battle_ptr`
argument, not a hidden global).

**Test:** `tests/test_state_copy.py` (`python tests/test_state_copy.py
[n_trials] [steps_to_replay]`). For each of 20 trials: start pointer A,
play 8 decisions forward with `baseline.choose()`, record the exact
selection history and A's resulting hand/active fingerprint; start a fresh
pointer B with the same two decks; replay the identical history on B;
compare fingerprints. Also checks, as a secondary property, that touching
pointer B never mutates pointer A's data (true isolation between
concurrently open pointers).

**Result (20 trials, 8 replayed decisions each):**

| Property | Result |
|---|---|
| States identical after replay (Q1 -- the actual requirement) | **0 / 20** |
| Isolation violations between concurrent pointers (Q2) | 0 / 20 |
| Exceptions/crashes | 0 / 20 |

**Verdict: NOT POSSIBLE. Per the plan's own stop condition, halting here --
Steps 2-5 are void as specified.** State-copying fails 20/20, not
intermittently -- confirming what earlier determinism testing already
established for this engine (`ablation_log.md`'s methodology notes,
2026-08-16: identical policy run twice produced different results both
times). `BattleStart`'s internal RNG governs deck shuffle and draw order,
is not seedable or otherwise observable/controllable from this API, and
replaying the same discrete selections on a fresh pointer does not force
the same shuffle -- so the reconstructed pointer B diverges from A immediately
(different opening hands) every single trial. Two independent findings worth
separating clearly:
- **What fails:** getting a second battle pointer into the *same* position
  as an existing live one. This is what Step 2 actually needs (one-ply
  rollout of the *current, real* game state) and it is not achievable with
  this engine's exposed API, full stop -- not a bug to work around, a
  missing capability.
- **What works:** two independent battle pointers can safely coexist
  (0/20 isolation violations, 0 crashes) -- concurrent self-play games
  (e.g. for generating Step 3's training data) are safe. Python-level
  `copy.deepcopy()` of an `obs_dict` also works fine (it's plain nested
  dicts/lists) but is inert -- there is no engine call that accepts a
  restored/copied state and continues simulating from it, so a deep-copied
  dict cannot be "applied to" in any way the real rules engine would honor.

**What this means for the rest of the proposal, stated plainly per the
constraints ("if any step fails to beat control, say so plainly and
stop"):** Step 2's one-ply rollout as specified -- copy the actual current
position, try each legal action against the real engine, evaluate the real
resulting position -- cannot be built. This is a clean negative result, not
a failure to find a workaround. It does **not** by itself rule out Step 3
in isolation (a value net trained on self-play *outcome* labels is a
separate, already-legal data pipeline -- self-play games run start-to-finish
normally, no mid-game branching needed), but Step 3 was specified as
feeding into Step 4's blend, which is specified as feeding into Step 2's
rollout. Reporting this now, as instructed, rather than silently
substituting a different Step 2 mechanism (e.g. blending the value net
directly into `baseline_score`'s per-option scoring without a real one-ply
lookahead) without the user's sign-off -- that would be a materially
different design than what was specified and asked for.

**User decision (2026-08-27):** scope narrowed to a decision type where a
"resulting position" can be constructed without engine branching at all --
retreat-target selection (`SelectContext.SWITCH`). Retreating/switching is a
pure relabeling of already-fully-visible data (which Pokemon is active vs
benched); no hidden information, no RNG, no coin flips are involved, unlike
attacks or draws. This also happens to be the same decision Candidate D
(retreat gating) targeted and came closest to the bar on (52.3%), so there's
independent reason to think there's real signal here.

## Learned value-net proposal -- Step 2 (adapted): switch-prediction validation

**Approach:** `src/switch_predict.py`'s `predict_post_switch()` constructs
the hypothetical post-switch `obs_dict` in pure Python (deepcopy + swap
active/bench, clear special conditions) for a candidate bench target,
without any engine call. Validated against real ground truth rather than
assumed correct: `tests/test_switch_prediction.py` predicts BEFORE each real
SWITCH decision during self-play, then actually applies the real selection
and diffs the real resulting position against the prediction -- using
`src/value_features.py`'s order-invariant feature vector (the same
representation Step 3's value net will consume) rather than a raw dict diff,
since exact bench-slot ordering isn't part of what the net needs to know.

**Bug caught by the validation test, not assumed away:** the first version
of `predict_post_switch` additionally subtracted `card.retreatCost` energy
from the retreating Pokemon. This double-counted: by the time a SWITCH
decision is presented, the engine has *already* resolved cost payment as an
earlier, separate decision (`RETREAT` -> an `ENERGY`-discard decision ->
*then* the `SWITCH` decision) -- the active's `energies` in the incoming
`obs_dict` already reflects that. The "Switch" trainer card (id 1123 in this
deck) reaches the identical `SWITCH` context with no cost step at all. First
run: 792/1107 SWITCH decisions across 200 games mismatched, isolated
entirely to the bench-energy-mean feature. Removed the cost-deduction logic
entirely (the incoming state is already correct, nothing more to subtract).

**Result after the fix (300 games):**

| Metric | Result |
|---|---|
| SWITCH decisions observed | 1,622 |
| Prediction mismatches | **0** |
| Exceptions | 0 |

**Verdict: PASS.** Not vacuous -- 1,622 real SWITCH decisions exercised
across 300 games, comfortably enough to trust the zero. `predict_post_switch`
is now a validated, engine-ground-truth-checked building block. Proceeding
to Step 3 (value net) using `src/value_features.py`'s feature vector.

---

## Learned value-net proposal -- Step 3: value network

**Architecture:** `src/value_net.py` -- pure NumPy (manual forward pass +
backprop + Adam), not PyTorch, matching `src/baseline.py`'s zero-extra-
dependency inference philosophy and the same reasoning that motivated
deleting the DQN pipeline's ML infra. `FEATURE_DIM (17) -> 32 (ReLU) -> 16
(ReLU) -> 1 (sigmoid)`, two hidden layers per spec, binary cross-entropy
loss.

**Data:** `tools/collect_value_data.py` runs M1-vs-M1 self-play and labels
every MAIN-context decision's position (72.1% of all decisions per the
Candidate-A instrumentation, ~113/game here) with the eventual winner, from
the perspective of whichever player was to move. Not literally *every*
decision of any context type -- MAIN is where "player to move" changes
meaningfully turn to turn, and `value_features.py` only encodes board
state, not context type, so this doesn't change the function being learned,
only avoids diluting the dataset with near-duplicate snapshots from mid-
resolution of a single compound action. 250 games -> 28,507 labeled
positions (0 draws, 0 exceptions), comfortably over the 20k floor. Label
balance 0.484 -- expected for a mirror M1-vs-M1 matchup.

**Methodology bug caught before trusting any number, not after:** the first
train/val split was position-level (random permutation over all 28k rows).
Positions from the same game are correlated -- early-game features for a
game player 0 goes on to win aren't independent samples of "how good is
this position," they're draws from one game's trajectory -- so a position-
level split let the same game appear on both sides and inflated the
held-out number. First (invalid) run: 71.95% held-out accuracy. Re-ran data
collection to tag every position with a `game_id`, then split by *game*
(50/250 games held out entirely, no held-out game's positions touch
training) -- corrected number: 63.36% accuracy, but train_loss kept
falling while val_loss rose after ~epoch 10 (0.5470->0.6458 while
train_loss dropped to 0.5233), a textbook overfitting signature, and
calibration was visibly overconfident at both extremes (predicted 0.96 in
the top bin vs actual 0.839). Added early stopping on val_loss (best
weights restored, patience=8) -- not rescue-tuning a failing result, this
is standard practice for "train to convergence" once train/val diverge, and
it's evaluated on the same held-out game-level split throughout.

**Result (final, early-stopped at epoch 13, held-out = 50 unseen games /
5,799 positions):**

| Metric | Value | Constant-predictor baseline |
|---|---|---|
| Accuracy | **62.32%** | 51.63% |
| Log loss | 0.6430 | -- |
| Brier score | 0.2265 | 0.2498 |

Calibration (held-out): predicted and actual win rates track closely across
bins with real sample counts (e.g. [0.4,0.5) pred 0.451 / actual 0.449;
[0.8,0.9) pred 0.833 / actual 0.844) -- no [0.9,1.0) bin has any held-out
samples post-early-stopping, network no longer emits overconfident extreme
predictions the way the overfit version did.

**Verdict: PASS, real but modest signal.** 62.3% vs a 51.6% baseline is a
genuine, above-chance, properly-validated result on unseen games -- not
overfitting-inflated, not vacuous, calibration is honest where sample
counts support it. It is not a strong signal (nowhere near board-state-
solving accuracy), consistent with a 17-feature summary vector that
deliberately omits hand contents, specific card identities, and attack
availability. Proceeding to Step 4 (blend into retreat-target scoring)
with this net, not a stronger/re-tuned version -- this is the number being
carried forward, honestly reported per the constraints ("if any step fails
to beat control, say so plainly and stop" -- this step did not fail, it
passed with a real, modest, disclosed effect size).

---

## Learned value-net proposal -- Step 4: blend, don't replace

**Implementation:** `src/baseline.py` gained a module-level config value
`VALUE_NET_WEIGHT` (default `0.0`) and a lazily-loaded, load-failure-safe
`ValueNet` singleton (missing checkpoint -> `None` -> heuristic-only
fallback, never a crash). The SWITCH-context branch (only SWITCH, not
TO_ACTIVE -- `predict_post_switch` is only validated for SWITCH per Step 2)
now computes `final = (1-w)*heuristic + w*value_net(predicted_post_switch)`
when `w > 0`; at `w = 0` the new code path is never even entered, so the
default behavior doesn't depend on the checkpoint existing at all.

**Pre-sweep regression tests (`tests/test_value_net_blend.py`), all
required before trusting any sweep number:**

| Check | Result |
|---|---|
| w=0.0 selections identical to `baseline_control.py`, decision-for-decision | PASS -- 8,002/8,002 decisions matched across 50 games |
| All 5 sweep weights run crash-free | PASS -- 0 exceptions at each of w in {0, 0.25, 0.5, 0.75, 1.0} |
| Missing checkpoint falls back gracefully (w=0.5, checkpoint forced absent) | PASS -- 0 exceptions |

**Sweep result (300 games each vs `baseline_control.py`, alternating
seats):**

| w | Win rate | Crashes | Fallbacks |
|---|---|---|---|
| 0.0 | 53.3% (160/300) | 0 | 0 |
| 0.25 | 49.0% (147/300) | 0 | 0 |
| 0.5 | 45.3% (136/300) | 0 | 0 |
| 0.75 | 54.0% (162/300) | 0 | 0 |
| 1.0 | 51.0% (153/300) | 0 | 0 |

**Verdict: FAIL. No w beats control by a margin distinguishable from
noise. Stopping here per the constraints ("if any step fails to beat
control, say so plainly and stop").** No monotonic trend against w --
scattered 45.3%-54.0% with no dose-response relationship, which is what
pure sampling noise around 50% looks like, not what a real graded effect
looks like. The single most useful data point in this table is **w=0.0
itself reading 53.3%** -- w=0.0 is proven byte-identical in behavior to
`baseline_control.py` (the regression test above confirms 8,002/8,002
decisions matched), so this specific 53.3% is *known*, by construction, to
be pure noise, not signal. That's a direct, in-sample demonstration that
this exact experimental setup (n=300, alternating seats) clears the 53%
bar by chance alone often enough to land there on a run that is
*definitionally* a no-op. Given that, treating w=0.75's 54.0% as a
candidate worth a bigger confirmation run would be cherry-picking the best
of five noisy draws after already having direct proof the noise floor
reaches that high unassisted -- the same trap the amendment about
1000-game confirmation exists to guard against, and not appropriate to
invoke selectively only for the reading that happens to look best.

**Plausible reasons the value net's real, validated Step 3 signal (62.3%
accuracy on held-out games) didn't translate into a game-level win-rate
improvement, offered as hypotheses, not confirmed:**
- SWITCH decisions are infrequent per game (~5.4/game, from Step 2's 1,622
  SWITCH decisions across 300 games) -- even a real per-decision
  improvement may be too diluted across a full game to move the needle on
  win rate at this sample size.
- Step 3's 62.3% accuracy is measured over *all* MAIN-context positions
  broadly, not specifically at the moment of a retreat decision -- the
  value net's marginal information *beyond* the existing bench-hp-fraction
  heuristic at exactly that decision type may be much smaller than the
  headline accuracy number suggests, since HP fraction is already a
  meaningful chunk of what determines win probability.
- Candidate D (retreat gating, hand-crafted) got the closest of any
  ablation candidate to the 53% bar (52.3%) without clearing it either --
  two independent approaches (hand-crafted heuristic, learned value net)
  both landing inconclusive on the same decision type is weak but
  consistent evidence that retreat-target selection specifically may not
  carry much win-rate leverage for this deck/matchup, rather than either
  approach being poorly executed.

**Step 5 (safety wrapper):** not built as new work -- moot given Step 4's
result, and already structurally satisfied regardless:
`_hard_override_switch`'s Rule 3 (never voluntarily retreat into a Pokemon
the opponent can KO for free) already runs in `hard_override()` before
`baseline_score` is ever consulted for SWITCH/TO_ACTIVE contexts, for any
value of `VALUE_NET_WEIGHT`. The blended score can only ever influence
which *safe* candidate is chosen, never override that filter.

**Final disposition:** `src/baseline.py` reverted to
`baseline_control.py`'s exact content (hash-verified identical,
`8DD8833B0C1D19DD616B2D145AD0AE0242DB52CB03B12D26E14FCFC7AC4E99F3`) -- the
blend code is real, tested, and correct, but wiring in a dependency on a
trained checkpoint for a measured-zero win-rate benefit isn't justified,
unlike Candidate F's kept regression test (a free safety net with no
performance claim attached). The blended `baseline.py` (the actual file the
sweep above was measured against) is archived at
`docs/writeup/rejected/value_net_blend.py`, matching the same convention
every rejected ablation candidate A-F already uses -- reconstructed from
the two edits applied during Step 4 after reverting, since it wasn't saved
before the revert the first time; caught and fixed before this section was
finalized. `tests/test_value_net_blend.py` was updated to load that
archived file directly (not `src.baseline`, which no longer has the blend)
and re-verified passing against it. The rest of the value-net
infrastructure is kept, tested, and documented as a deliverable of this
exercise, available to revisit, but not part of the active decision path:
`src/value_features.py`, `src/switch_predict.py`, `src/value_net.py`,
`tools/collect_value_data.py`, `tools/train_value_net.py`,
`tests/test_state_copy.py`, `tests/test_switch_prediction.py`,
`tests/test_value_net_blend.py`, `ckpt/value_net.npz`,
`data/value_net/positions.npz`.

**Summary for the Strategy Writeup:** a well-specified, staged proposal
(state-copy check -> validated prediction -> trained-and-validated value
net -> swept blend) that failed at the last, most important gate -- moving
the actual win-rate needle -- despite every earlier stage passing on its
own terms. This is exactly the kind of negative result worth reporting
plainly rather than reshaping into a false positive: Step 1 found a hard
engine limitation and the scope was honestly narrowed in response; Step 3
found and fixed a real data-leakage bug before trusting its own number;
Step 4 then showed that even a properly-validated learned signal doesn't
automatically translate into a measurable game-level improvement when
applied to an infrequent decision type. Six rule-based ablation candidates
and one learned-evaluator proposal later, `src/baseline.py` remains
byte-identical to `baseline_control.py`.

---
