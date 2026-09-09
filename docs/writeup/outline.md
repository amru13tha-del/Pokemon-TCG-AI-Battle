# Strategy Writeup Outline — PTCG AI Battle Challenge

Judging (from the Rules tab, confirmed 2026-08-16): **Model Score 70%** (articulated
rationale, hypotheses tested, technical soundness, consistency under repeated
matches, avoiding over-reliance on situational advantages, performance within
track), **Deck Score 20%** (deck concept clarity, key-card selection/utilization),
**Report Score 10%** (structure, use of figures/charts/tables). Hard cap: 2000
words total (Media Gallery is separate/optional and doesn't count against it).

Every number below is something we actually produced — the file it came from is
cited so it's checkable, and every fluctuating/live figure (ladder scores) is
marked as such rather than frozen into a false-precision number. All seven
sections now have full draft prose (updated 2026-08-27, after the RL/DQN
pipeline was deleted and replaced with a pure rule-based agent plus a
tested-and-rejected value-net episode — §2/4/5/7 were rewritten from their
original, now-stale DQN-era drafts; §3/6 were drafted from scratch). Draft
prose is marked with `>` blockquotes and is close to paste-ready; word counts
per section are noted where they were checked and may run slightly over the
per-section budget below, within the document's overall buffer.

---

## 1. Introduction / Approach Summary — 150 words
**Maps to:** Model Score (articulation)

**Must argue:** what kind of problem this is (two-player, zero-sum, stochastic,
imperfect-information, variable action space — rules out plain minimax and a
fixed-head DQN) and the resulting architecture choice: a rule-based policy,
built up and refined in verified, falsifiable stages — including two
attempts to add a learned component that were tested and honestly rejected
— rather than assumed correct from a single design pass.

**Draft prose (ready to paste, ~140 words):**

> Pokémon TCG is two-player and zero-sum, but stochastic (shuffled decks,
> coin-flip effects) and imperfect-information (the opponent's hand and
> deck order are hidden), with a legal-action set that changes size and
> meaning at every decision. That rules out plain minimax — there's no
> single deterministic tree to search — and a fixed-output-head network,
> since option index 3 means something different at every decision point.
>
> The approach taken was a rule-based policy, hardened and tested in
> verified stages rather than assumed correct from one design pass: a
> small set of hard-coded overrides for game-critical decisions (lethal,
> trade-up knockouts, unsafe retreats), a heuristic scorer for everything
> else, six single-change candidate improvements each evaluated against a
> frozen control, and one attempt to add a learned value net — validated
> end to end, but ultimately rejected on the numbers. Every claim in this
> report is backed by a number that was actually measured, not assumed.

**Gap:** none — matches what's actually submitted.

---

## 2. System Architecture — 450 words
**Maps to:** Model Score (technical soundness, originality)

**Must argue:** the three-layer safety design (zero-dependency fallback ←
uniform-random legal ← rule-based policy) and why the *rule-based* policy —
not a trained network — is what actually ships, with the hard-override /
heuristic-scoring split explained precisely enough that "how" is unambiguous.

**Draft prose (ready to paste, ~420 words):**

> The submitted agent is a three-layer safety architecture wrapping a
> single rule-based decision policy. The outermost layer, `main.py`'s
> `agent()`, is wrapped so it can never propagate an exception: any
> failure is logged to stderr and falls through to a zero-dependency
> fallback that reads only the raw legal-option count. The middle layer
> falls back to a uniformly-random legal action if the policy layer
> fails. The innermost, normally-active layer is `src/baseline.py`.
>
> Three hard-override rules run before any heuristic scoring is
> consulted, and take priority whenever they fire: take a lethal attack
> if it wins the game outright; take a non-lethal knockout that trades
> our single-prize attacker for a multi-prize opponent Pokémon; never
> voluntarily retreat into a Pokémon the opponent can knock out for free
> next turn if a legal alternative exists. All three are grounded
> directly in the compiled engine's own source, not assumed from general
> rules: weakness doubling and resistance's flat −30 damage reduction are
> cited to specific line numbers in the engine's `SetProperty.h`, and it
> was confirmed that the *attacking Pokémon's own type* — not the
> attack's energy cost — is what's compared against weakness/resistance,
> a distinction easy to get wrong. Below the hard overrides, every
> remaining decision (attaching energy, playing a trainer, retreating,
> resolving multi-target selections) is scored by a context-specific
> heuristic and the highest-scoring option is chosen.
>
> This architecture was arrived at, not assumed. An earlier attempt
> reintroduced a trained neural network — first a full Deep Q-Network
> policy, later a smaller supervised value net blended into one specific
> decision type — but neither improved on the hand-tuned heuristic after
> honest evaluation (see §4 and §6). The final submission is the pure
> rule-based policy: simpler, faster, and with zero runtime dependencies
> beyond the Python standard library and the competition's own engine
> bindings. This was confirmed by tracing every module actually loaded
> during a real game, not just reading imports statically: only stdlib
> modules (`ctypes`, `json`, `dataclasses`, `enum`, `collections`) plus
> the engine wrapper appear, with zero third-party packages reachable
> from the entry point.
>
> Correctness was verified the same way. A dedicated regression test
> asserts the agent never selects END while a legal attack exists at that
> decision — closing a scoring-tie edge case that provably cannot occur
> with the current deck's card pool, but is defended against regardless,
> in case the deck changes. Before every upload, the packaged submission
> artifact is extracted fresh and re-run decision-for-decision against a
> frozen control copy of the scoring logic, with no repo path on
> `sys.path`. Per-decision latency, measured over a full game from that
> packaged, cold-started artifact, averages 0.027ms with a 0.259ms
> maximum — negligible against any plausible per-move budget.

**Gap:** none load-bearing — the architecture described is exactly what's
submitted. The trained-network attempts are covered honestly in §4/§6 as
tested-and-rejected, not implied to be silently running.

---

## 3. Deck Design & Rationale — 300 words
**Maps to:** Deck Score (20%, entirely this section)

**Draft prose (ready to paste, ~300 words):**

> The deck runs three single-prize Basic Pokémon — Throh (130 HP), Landorus
> (120 HP), and Terrakion (140 HP) — all pure Fighting-type, on a fully
> Fighting-energy base: 16 Basic Fighting Energy plus Cheren, Ultra Ball,
> Fighting Gong, Poké Pad, Boxed Order, Switch, Premium Power Pro, Lively
> Stadium, and Crushing Hammer.
>
> All-Basic is the load-bearing decision, not a card-power choice. Our agent
> is a greedy per-decision scorer with no multi-turn setup planning, so an
> evolution line would need planning capability it doesn't have. Going
> all-Basic removes that requirement: every attacker is playable turn one,
> with no risk of a dead pre-evolution stranded in hand.
>
> Single-prize is the deck's actual thesis. Every attacker costs the
> opponent exactly one prize on knockout. Since the agent doesn't reason
> about prize-race tempo or defend its board positionally, the deck is
> built so that even a bad trade it walks into is capped at a one-prize
> loss — robustness to the agent's own limitations, not just raw stats.
> Card selection also filtered out flashier options (Iron Boulder, Mesprit,
> Victini) despite higher raw damage, because their attacks carry "does
> nothing if [condition]" clauses; every attack in the final deck has an
> unconditional or purely beneficial-condition damage floor — a deliberate
> hedge against over-reliance on situational advantages.
>
> The three attackers cover different roles on one shared resource: Throh
> is the best damage-per-energy; Landorus pokes cheaply and recycles its
> own energy back to hand; Terrakion punishes a prior knockout (Retaliate)
> and carries a flat, caveat-free finisher. All run on pure Fighting
> energy, so nothing drawn is ever type-stranded. The trainer line
> reinforces this: every search effect finds something immediately
> playable because the whole deck is Basic, Switch de-risks the agent's
> known-imperfect retreat judgment, and Lively Stadium's +30 HP is
> asymmetric in our favor since we run 100% Basics.
>
> Validated: 88.5% win rate vs. a random-legal baseline, 0 crashes, 0
> fallbacks over 200 games.

**Gap:** this deck has a known, deliberately-accepted weakness — see §6 for
the framing. It has also been tested against exactly one named external
opponent (Kaggle's sample deck) plus the random-legal baseline; no broader
matchup sample yet. **Fillable in 4 weeks** if 2-3 more test decks get
built — flagged again in §7.

---

## 4. Hypotheses Tested & Confirmed Scope Decisions — 300 words
**Maps to:** Model Score (hypotheses tested, originality, avoiding overclaiming)

**Must argue:** specific, falsifiable decisions that were tested against the
live engine rather than assumed — the throughline is "we checked before
claiming," which is the concrete form "avoiding over-reliance on situational
advantages" takes in code.

**Draft prose (ready to paste, ~330 words):**

> Every improvement attempt was tested against the live engine and a
> frozen control baseline, not assumed from theory, and negative results
> were kept rather than discarded.
>
> Coin-flip and conditional attack bonuses are real in this card pool but
> deliberately not modeled in lethal detection: confirmed live that the
> engine's exposed attack-damage field is already the coin-independent
> floor (a four-coin attack with a per-heads bonus exposes `damage=0`; a
> "+20 if heads" attack exposes `damage=20`). Hard-override lethal checks
> use only this floor, so they can miss a coin-dependent lethal but never
> misfire a false one. Separately, the deck-legality checker's ACE SPEC
> ≤1 rule was silently unenforced until cross-checked against the live
> engine's own card-data field — a real bug caught by verification, not
> a hypothetical one.
>
> Six single-change scoring candidates were each implemented in isolation
> and evaluated over 300 games against a frozen control: role-aware
> energy attachment regressed sharply (31.3% win rate) from a real,
> root-caused interaction bug between two scoring rules, not noise;
> retreat gating (52.3%) and supporter-play ordering (49.3%) showed no
> reliable signal; a correctness fix for three previously-unhandled
> decision contexts (45.7%) targeted contexts either mathematically
> incapable of mattering for this deck or vanishingly rare; a fix
> guaranteeing a legal attack is never passed up for ending the turn
> (50.7%) was proven mathematically inert for this deck's specific card
> pool, independent of its win-rate reading; a KO-first attack-selection
> idea was found already implemented, so nothing changed. All six were
> rejected by the same ≥53%-win-rate gate, applied without exception.
>
> A subsequent, more careful attempt built a small value net to help
> specifically with retreat-target scoring, validating every stage
> against real engine ground truth before trusting it — catching and
> fixing two real bugs along the way (a double-counted retreat cost, and
> a data-leakage bug in the train/val split that had inflated an early
> accuracy reading from 71.95% to an honest 62.3%). Even so, blending it
> into scoring failed to beat control at any tested weight — reported as
> a clean negative result, not reframed as a partial success.

**Gap:** none — this is the section's content. If time allows, a seventh
candidate targeting a different decision type would be the natural next
falsifiable test, not a repeat of the retreat-scoring sweep.

---

## 5. Performance Results — 200 words
**Maps to:** Model Score (performance within track) + Report Score (this is the
natural home for a table/chart)

**Must argue:** a compact, honest scoreboard across milestones — this section is
where a results table earns its Report Score credit.

**Evidence (put in a table):**

| Stage | Metric | Result | Source |
|---|---|---|---|
| M0 | vs random legality | 200 games, 0 exceptions, 0 illegal actions | `tests/test_legality.py` |
| M1 | win rate vs M0 | 91.5% (183/200), 0 crashes, p99 latency 0.063ms | `tools/evaluate.py` |
| Deck redesign | win rate vs random | 88.5% (177/200), 0 crashes | `tools/evaluate.py` (post-redesign) |
| Ablation (6 candidates) | win rate vs frozen control | all 6 rejected — 45.7%, n/a (already satisfied), 31.3%, 52.3%, 49.3%, 50.7% | `docs/writeup/ablation_log.md` |
| Value net | held-out prediction accuracy | 62.3% vs. 51.6% constant-predictor baseline (28,507 positions, game-level split) | `tools/train_value_net.py` |
| Value net blend | win rate vs. control, 5 weights swept | no weight beat control (45.3%–54.0%, no trend) | `docs/writeup/ablation_log.md` |
| Ladder | public score (live, fluctuates) | M0 = 306.0, M1 = 475.1, M1+new deck = **256.1** (most recently confirmed via `kaggle competitions submissions`) | `kaggle competitions submissions` |

**Gap:** ladder scores are a live Gaussian rating, not a settled number — cite
that it was checked live and note it will keep moving, rather than a fixed
date (re-checking this same submission history minutes apart already showed
M1 move from 415.3 to 475.1 and M1+deck move from 264.2 to 256.1 — cite the
number, not a snapshot date, since the date alone doesn't guarantee
reproducibility). The redesigned-deck submission currently scores *below*
the pre-redesign M1 submission on the live ladder (256.1 vs. 475.1, a gap
of ~219 points — wider than the ~151-point gap observed at the previous
check) — the opposite of what local 200-game testing predicted.
**See §6 — this isn't an isolated anomaly, it's read together with two other
findings there as one connected limitation, not explained away here in
isolation.**

---

## 6. Design Tradeoffs & Known Limitations — 300 words
**Maps to:** Model Score (consistency, avoiding over-reliance on situational
advantages — this section is where the *limits* are shown to be understood,
which the rubric explicitly rewards over pretending there aren't any)

**Draft prose (ready to paste, ~300 words):**

> Local evaluation, not agent architecture, was this project's real
> limiting factor — three findings point at one conclusion. A known-null
> case makes it concrete: blending in a value net at weight w=0 is
> provably byte-identical to the control (8,002/8,002 real decisions
> matched), yet the standard 300-game mirror-match evaluation still read
> that known-null case at 53.3%, a 3.3-point deviation from noise alone.
> Measured against that noise, the six ablation candidates split in two:
> a role-aware energy-attachment regression (31.3%) was root-caused to a
> real code-level bug, and a scoring fix (50.7%) was proven mathematically
> inert for this deck — both stand independent of noise. The other four
> (45.7%, 52.3%, 49.3%, and the value-net blend's 45.3%-54.0% spread) sit
> inside that same noise band — honest non-detections, not proof the
> ideas don't work. Separately, the deck redesign scored 88.5% locally
> against a random-legal opponent, then landed ~220 rating points below
> the pre-redesign submission on the live ladder (256.1 vs. 475.1, a gap
> that widened, not narrowed, on re-check) — consistent with the same
> weak-evaluation problem (a random-legal
> opponent and mirror-match self-play are both low-information proxies
> for the ladder's real opponents), but not proof of that specific cause;
> opponent-pool composition and the deck's outlier weakness (below)
> remain live alternatives.
>
> A genuine platform limitation surfaced during the value-net work: the
> engine exposes no state-copy or clone API, so true one-ply lookahead
> cannot be built — confirmed by direct testing, not assumed. This
> forecloses search-based improvement without reimplementing game rules
> from scratch, judged out of scope.
>
> The deck itself carries one deliberately-accepted weakness: it loses
> badly, head-to-head, against Kaggle's own sample deck, whose Mega
> Abomasnow ex attack exceeded the deck's realistic HP ceiling in testing
> — treated as an outlier matchup rather than a reason to abandon the
> single-prize efficiency thesis.
>
> All win-rate figures here are single-run samples without confidence
> intervals — a reporting gap, inexpensive to close with larger batch
> runs before final submission.

**Gap:** no confidence intervals / variance reporting on any win-rate
number (all single-run 200-300-game samples). **Fillable in 4 weeks** with
larger batch runs via the existing `tools/evaluate.py`.

---

## 7. Conclusion / Future Work — 100 words
**Maps to:** Model Score (wraps the argument), Report Score (closes the structure)

**Must argue:** what's proven vs. what's aspirational, stated plainly.

**Draft prose (ready to paste, ~105 words):**

> This project shipped a rule-based agent whose every design decision —
> the deck's all-Basic, single-prize structure, each of six candidate
> scoring changes, and a value-net addition — was tested against the live
> engine and a frozen control rather than assumed. Six candidates and one
> learned-evaluator attempt were rejected; each rejection is logged with
> its root cause, not just its number. What's proven: a correct, fast,
> dependency-free rule-based policy that beats a random baseline
> decisively and holds up under its own regression suite. What's
> aspirational: replacing mirror-match self-play and a random-legal
> opponent with evaluation that better predicts live performance (§6),
> broader external matchup testing, and revisiting a learned evaluator
> with real search if the engine ever exposes state-copying.

**Gap:** none — this directly reflects what's submitted (M1's rule-based
policy plus the redesigned deck) with no implied-but-not-shipped component.

---

## Total (updated, live ladder scores re-verified): budgeted 150+450+300+300+200+300+100 = 1800 words

All seven sections have full draft prose. Actual drafted prose, checked by
word count: §1=150, §2=437, §3=314, §4=337, §6=318, §7=117 — **1,673 words**,
plus §5's table + short notes (not counted the same way; estimate another
100-140 words once the table is transcribed into the Writeup editor, larger
than before since §5's gap note grew to explain the re-checked ladder
numbers). That puts the realistic total around **1,773-1,813 words** — this
is now close enough to the 2000-word cap that it needs a trim during final
assembly, not just a buffer to absorb. §4 and §6 grew most (Candidate F was
missing from §4's narrative despite being cited by number in §6; both were
corrected for accuracy, not padded). **Do a real word count on the final
assembled document in Kaggle's actual Writeup editor before submitting, and
trim §2 (currently under its own budget, the easiest place to cut) if the
real count lands over 1900.**

**On the ladder numbers specifically:** these are a live rating and will
keep moving. Re-checking the same three submissions minutes apart already
showed real movement (M1: 415.3 → 475.1; M1+deck: 264.2 → 256.1) — cite
whatever the live number is when the Writeup is actually finalized, not the
numbers frozen in this outline, and say so is a live figure rather than
implying a fixed snapshot date guarantees reproducibility.

## Gap summary, sorted by fillability before 2026-09-13

| Gap | Fillable in 2 weeks? | How |
|---|---|---|
| §3/4/6 run over their sub-budgets (69 words combined — §4 +37 is now the largest, after adding Candidate F) | **Yes — quick** | Trim during final assembly; §2 is 13 words *under* its own budget, the easiest place to cut from to offset |
| No confidence intervals on win-rate claims | **Yes** | Re-run `tools/evaluate.py` / the ablation harness at higher `--games` — this is also the fix for the noise-floor problem §6 identifies, not just a reporting nicety |
| Deck tested against only one named opponent + random | **Yes, if prioritized** | Build 2-3 more test decks against real (non-mirror-match, non-random) opponents — this is the direct fix for the weak-evaluation limitation §6 argues is the project's real bottleneck |
| Ladder redesigned-deck score (256.1) currently *below* pre-redesign M1 (475.1), gap widened on re-check (was 264.2 vs 415.3) | **Reframed, not resolved** | §6 now reads this together with the w=0 noise-floor finding and the ablation candidates' split verdicts as one connected "local evaluation didn't predict live performance" conclusion — not proven causally, stated as consistent-with, not solved |
| Ladder score is a live/unsettled figure that already moved during this session | **No, not under our control** | Cite the number as live, checked at document-finalization time — not a frozen snapshot date, which this session's own re-checks show isn't a stable enough anchor |
