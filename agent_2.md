# agent.md — PTCG AI Battle Challenge: Q-Network Agent

**Project:** An agent for *The Pokémon Company — PTCG AI Battle Challenge (Simulation)* on Kaggle.
**Method:** Deep Q-Network (DQN), adapted for a **variable-size legal action set** under
**imperfect information**, wrapped in a rule-based safety layer.
**Audience:** an agentic coding tool (Claude Code / Cursor / Antigravity) working in this repo.

---

## 0. Prime directives — read before writing any code

1. **Never invent the API.** The exact shape of `obs_dict`, the deck file format, and the
   submission bundle layout are defined by the official Kaggle starter notebook, `ptcg_engine/`,
   and `sample_submission/`. Read those files first. If a field name is not confirmed in the
   official material, do not use it — write a `TODO(verify)` and ask.
2. **The engine is ground truth, not the rulebook.** `cri_rulebook_en.pdf` explains the game to
   humans. Where a heuristic and the engine disagree, the engine wins. Rules knowledge is used
   only for *shaping and heuristics*, never to predict legality.
3. **Never return an illegal action.** The environment hands the agent a list of legal options.
   The agent returns indices **into that list**. Anything else is a loss.
4. **Never crash, never time out.** A crash is scored as a loss. Every decision path ends in
   `_legal_fallback(obs)`. Wrap the whole policy in `try/except Exception`.
5. **Ship the smallest thing that scores first.** A valid submission on the ladder beats a
   brilliant untested one. Milestone M0 comes before any neural network exists.
6. **No network access at inference.** No API calls, no downloads, no LLM in the loop. The
   submission runs offline on CPU with a per-move time limit.
7. **Do not redistribute competition assets.** Card images, card data and engine code stay out of
   any public repo, gist, or write-up.

---

## 1. Competition facts (verify each against the Kaggle page before relying on it)

| Item | Value | Status |
|---|---|---|
| Simulation track | `pokemon-tcg-ai-battle` — automated ladder, Gaussian skill rating (μ) | verify |
| Simulation final submission | **2026-08-16** | verify — this may already have passed |
| Strategy track | `pokemon-tcg-ai-battle-challenge-strategy` — Kaggle Writeup + media | verify |
| Strategy final submission | **2026-09-13** | verify |
| Submission artifact | `submission.tar.gz` containing `main.py`, `deck.csv`, engine `cg/` at top level | verify against `sample_submission/` |
| Rate limit | ~5 submissions/day; the most recent 2 count for standings | verify |
| Engine | `cabt`, running under `kaggle-environments` (pin the ladder's version, e.g. `1.30.1`) | verify |
| Card pool | ~2,000 Standard-format cards; IDs in `EN Card Data.csv` | verify |

**Agent contract (this is the load-bearing one):**

```python
def agent(obs_dict) -> list[int]:
    """
    Normal decision points -> a list of option indices into the legal-option list.
    Deck-selection context   -> a list of 60 card IDs.
    Must never raise. Must never exceed the per-move time budget.
    """
```

Confirm from the sample agent: whether the return is always a list, when a multi-element list is
expected (multi-select contexts such as discarding N cards), and the name of the field carrying
the decision context (a `SelectContext`-style enum in the sample).

---

## 2. What kind of game this is (and why that dictates the architecture)

Classify the problem honestly, because it rules several classic techniques out:

- **Two-player, zero-sum** — one player's gain is the other's loss. Self-play is valid; the same
  network can pilot both seats.
- **Stochastic** — shuffled decks, coin flips, random targets. There is no single "next state";
  there is a distribution over next states. Deterministic tree search is not directly applicable.
- **Imperfect information** — the opponent's hand, both decks' orders, and the identity of the
  prize cards are hidden. The agent observes a *belief-relevant slice*, not the true state.
  Formally this is a POMDP, not an MDP.
- **Enormous, context-dependent action space** — the legal option list changes size and *meaning*
  at every decision point (attach energy / play a Trainer / choose a target / choose which cards
  to discard / choose an attack).

Consequences:

- **Minimax + alpha-beta pruning: not usable as the main policy.** They assume perfect
  information and determinism. In PTCG the opponent's hand is unknown and the deck is shuffled,
  so a minimax tree has chance nodes and unobservable state at every ply. Alpha-beta prunes
  nothing meaningful there. *Narrow* exception: a depth-1 **expectiminimax lethal check** on the
  current turn ("can I KO right now, accounting for coin flips?") is cheap and worth having as a
  hard override — see §7.
- **Vanilla DQN with a fixed output head: not usable either.** The Gridworld DQN in the reference
  article outputs a 4-vector because Gridworld always has exactly 4 actions with stable meanings.
  Here, output index 3 means "attach Fire Energy" in one state and "discard Ultra Ball" in the
  next. A fixed head learns nothing coherent. **This is the single most important adaptation in
  this project.**
- **What does work:** a Q-network scored **per (state, option) pair**, plus experience replay, a
  target network, Double-DQN targets and ε-greedy — i.e. the DQN machinery, re-plumbed for a
  variable action set. Later, optionally, determinized search (IS-MCTS) using the Q-net as the
  leaf evaluator.

---

## 3. The core architecture: option-scoring Q-network

```
                 s (state features, fixed length D_s)
                        |
                 [ state encoder MLP ]  -> h_s (128)
                        |
       for each legal option o_i (features, fixed length D_o)
                        |
                 [ option encoder MLP ] -> h_oi (64)
                        |
        concat(h_s, h_oi) -> [ head MLP ] -> Q(s, o_i)   (scalar)
                        |
             argmax over i  (ε-greedy during training)
```

Properties this buys us, all of which matter:

- **Permutation invariance.** Reordering the option list reorders the scores identically. Index
  semantics no longer have to be memorised.
- **Variable action count.** 3 options or 60, same network.
- **Generalisation across cards.** Because an option is described by *features* ("this is a
  Supporter that draws to 5", "this attack does 230 for 3 energy") and not by an ID one-hot, the
  network transfers knowledge to cards it saw rarely.
- **One forward pass per decision.** Batch all legal options into a single `(N_options, D)`
  tensor. Essential for the time limit.

**Learning rule (Double DQN):**

```
y = r                                        if s' is terminal
y = r + γ · Q_target(s', argmax_{o'} Q_online(s', o'))   otherwise

loss = SmoothL1( Q_online(s, o_taken), y.detach() )
```

Double DQN (action chosen by the online net, valued by the target net) rather than plain
`max Q_target`, because plain DQN over-estimates badly in long stochastic episodes.

Hyperparameters to start from and then tune:

| Param | Start | Note |
|---|---|---|
| γ (discount) | 0.997 | Episodes are long — hundreds of decision points, not tens. A low γ makes the agent greedy and it loses the long game. |
| Learning rate | 1e-4, Adam | 1e-3 (Gridworld's value) is too hot here. |
| Replay buffer | 300k transitions | Prioritised replay is a later upgrade, not a v1. |
| Batch size | 256 | |
| Target net sync | every 2,000 gradient steps (hard copy) | Or Polyak τ=0.005. |
| ε schedule | 1.0 → 0.05 over ~40% of training, then hold | Anneal on *steps*, not episodes. |
| Warmup | 20k transitions before the first update | |
| Optimiser clip | grad-norm 10 | |

**Do not** copy the reference article's online, single-transition, no-replay training loop. It
overfits to one board — that article's own conclusion. Replay buffer + target network from day
one.

---

## 4. Feature encoding

Build this in **one isolated module**, `features.py`, with a single seam to the engine:
`obs_to_state(obs) -> np.ndarray` and `option_to_features(obs, option) -> np.ndarray`.
Everything downstream depends only on these two functions, so a schema change costs one file.

### 4.1 State features (`D_s`, target ~200–400 floats)

Observable only. Grouped:

- **Prizes:** own prizes remaining (one-hot 0–6), opponent prizes remaining (one-hot 0–6),
  the difference. *Highest-signal feature in the game — it is the win condition.*
- **Active Pokémon, both sides:** current HP / max HP, damage counters, type (one-hot), stage,
  retreat cost, attached energy by type (counts), tool attached (bool), status conditions
  (asleep / paralyzed / confused / poisoned / burned), whether it is an ex/Mega (prize value 2–3).
- **Bench, both sides:** for each of up to 5 slots, a compact version of the above + an
  occupancy bit. Also: bench count, count of KO-able bench targets.
- **Hand (own):** size, and category counts — Basic Pokémon, evolution cards playable *this turn*,
  Supporter available (bool), Item count, energy count, switch/gust effects available (bool each).
- **Opponent hand:** **count only.** Nothing else is observable.
- **Deck / discard:** own deck size, own discard composition summary (energy count, key Pokémon
  count), opponent discard summary. Prize identity is hidden — never encode it.
- **Turn context:** turn number (scaled), whose turn, energy-attached-this-turn flag,
  supporter-played-this-turn flag, retreat-used flag, first-player flag, stadium in play (one-hot
  over a small set + "other").
- **Derived tactical bits (cheap, high value):** can my active KO their active this turn (from the
  expectiminimax check, §7); can their active KO mine next turn; is a gust effect in my hand and
  is there a juicy bench target.

### 4.2 Option features (`D_o`, target ~60–120 floats)

- Option kind one-hot: play Basic / evolve / attach energy / play Item / play Supporter /
  play Stadium / play Tool / retreat / attack / pass / choose-target / discard-select / other.
- If it is an **attack**: base damage (scaled), energy cost, does it hit for weakness on their
  active, expected damage after weakness/resistance, is it lethal on their active, self-damage,
  energy discard cost, coin-flip dependence (bool + expected multiplier).
- If it is a **card play**: card category, a small learned embedding of the card ID
  (`nn.Embedding(n_cards, 16)`) **plus** hand-written attributes from `EN Card Data.csv` so rare
  cards are not cold. Draw count, search targets, disruption flag.
- If it is a **target choice**: the target's HP fraction, prize value, energy attached, is-KO flag.
- **Static prior score** from the rule-based baseline policy (§7) as one extra float. Giving the
  network the heuristic's opinion as an input speeds up early learning enormously.

Fit the card-attribute lookup at build time into a small `card_features.npz` keyed by card ID —
do not parse the CSV at inference.

### 4.3 The information-leak trap

If the local engine exposes hidden state (opponent hand, deck order, prize contents) during
training, **it must never reach `obs_to_state`.** A network trained on leaked features scores
beautifully locally and collapses on the ladder. Add a unit test: `obs_to_state` called on a
full-information state and on its masked version must produce identical output.

---

## 5. Reward design

Terminal reward dominates; shaping is a small nudge to fix credit assignment across the hundreds
of decision points in a game.

| Event | Reward |
|---|---|
| Win the game | **+1.0** |
| Lose the game | **−1.0** |
| Take a prize card | +0.10 |
| Give up a prize card | −0.10 |
| KO opponent's Pokémon | +0.03 |
| Own Pokémon KO'd | −0.03 |
| Per decision point | −0.0005 (mild pressure to close games) |
| Illegal / fallback action taken | −0.05 and log it loudly |

Rules of thumb: keep the sum of all shaping over a typical game below ~0.5 so it cannot outvote
the ±1 terminal signal; and run one training config with shaping *off* to confirm shaping is
helping rather than teaching the agent to farm prizes while losing.

---

## 6. Training pipeline — in this order

**Stage A — Imitation / behaviour cloning (do this before RL).**
Kaggle publishes a daily export of top-rated episode replays; replays are also downloadable via
the Kaggle CLI. Parse them into `(state, options, chosen_option)` tuples and train the same
network as a **classifier** (cross-entropy over the option scores, softmax across legal options).
This gives a policy that already plays sensible Pokémon before a single self-play game. Cold-start
DQN in a 2,000-card game is hopeless; BC initialisation is not optional in practice.

**Stage B — Self-play DQN.** Initialise from the BC weights. Play the agent against (a) a frozen
older copy of itself, (b) the rule-based baseline, (c) 2–3 known meta decks. Maintain an opponent
pool and sample from it — training only against the current self produces a policy that beats
itself and nothing else.

**Stage C — Ladder A/B.** Local evaluation misranks agents. The published experience from other
competitors is blunt about this: simple decks piloted cleanly outperform complex decks piloted
clunkily, and only the real ladder reliably ranks agents. Submit variants, compare μ, iterate.

**Deck choice is at least as important as the policy.** Pick one consistent archetype and commit;
`deck.csv` is a fixed 60 IDs for the whole ladder run. Prefer a deck whose lines are short (fewer
Stage-2 chains) so a learned policy has fewer ways to misplay it. Note the ex/Mega-ex prize
economics: those cards give up 2–3 prizes when KO'd, which is why single-prize attackers and
counters to ex-immunity effects periodically dominate the meta.

---

## 7. The rule-based layer (safety net + prior + fallback)

The neural net does not run unsupervised. Three jobs for hand-written code:

1. **Hard overrides.** Before consulting the Q-net:
   - If an attack is lethal on the opponent's active *and* taking that KO wins the game
     (prizes remaining ≤ prizes gained), take it. Depth-1 expectiminimax over coin flips:
     `E[damage] = Σ P(outcome) · damage(outcome)`; require `P(KO) ≥ 0.9` or guaranteed.
   - Never retreat the active into a lethal-next-turn state when a legal alternative exists.
   - Always play the free-value engine cards (draw supporters when hand is dead, etc.) unless the
     Q-net's margin over the alternative exceeds a threshold.
2. **Prior score.** `baseline_score(obs, option) -> float` is fed to the network as a feature
   (§4.2) and is the tie-breaker when Q-values are within ε of each other.
3. **`_legal_fallback(obs)`.** Returns a guaranteed-valid response for every context, including
   deck selection. This function must have **zero** dependencies on numpy, torch, or any file
   loaded at runtime — it has to work even when everything else has failed.

```python
def agent(obs_dict):
    try:
        with time_budget(MOVE_BUDGET_MS):
            return policy(obs_dict)
    except Exception:
        return _legal_fallback(obs_dict)
```

---

## 8. Inference constraints

- **CPU only, tight per-move budget.** Assume no GPU.
- **Export weights to `weights.npz` and run inference in pure NumPy** in the submission. A 3-layer
  MLP is ~20 lines of NumPy. This removes torch from the bundle: smaller archive, no import-time
  cost, no version-mismatch surprises. Keep PyTorch for training only.
- Batch every legal option into one matmul. No Python loop over options.
- Measure p50 / p99 decision latency and assert p99 is comfortably under the limit. Add a
  wall-clock guard: if the budget is 80% spent, return the baseline heuristic's choice.
- Deterministic at inference: `argmax`, fixed seed, no sampling.

---

## 9. Repository layout

```
repo/
  main.py                # THE submission entrypoint: agent(obs_dict). Self-contained + numpy.
  deck.csv               # 60 card IDs. Format copied exactly from sample_submission.
  weights.npz            # exported Q-network weights
  card_features.npz      # precomputed per-card attribute vectors
  agent.md               # this file
  README.md
  src/
    features.py          # obs_to_state, option_to_features  <-- the ONLY engine seam
    baseline.py          # rule-based policy, prior scores, hard overrides
    qnet.py              # torch model definition
    replay.py            # replay buffer
    train_bc.py          # Stage A: behaviour cloning from replays
    train_dqn.py         # Stage B: self-play DQN
    export_weights.py    # torch -> weights.npz
    parse_replays.py     # Kaggle episode replays -> BC dataset
  tools/
    build_submission.py  # pack main.py + deck.csv + weights + engine cg/ -> submission.tar.gz
    evaluate.py          # N games vs baseline / meta decks, report win rate + latency
  tests/
    test_legality.py     # 500 random games, zero illegal actions, zero exceptions
    test_no_leak.py      # masked vs unmasked obs produce identical features
    test_latency.py      # p99 decision time
  docs/
    official/            # Kaggle-provided engine, card data, sample notebooks (gitignored)
```

---

## 10. Milestones and acceptance criteria

**M0 — Valid submission (do this first, today).**
`main.py` picks a uniformly random legal option; `deck.csv` is a known working list. Bundle builds,
uploads, plays a full game on the ladder without error.
*Accept:* a scored submission appears on the leaderboard.

**M1 — Rule-based baseline.**
`baseline.py` with the §7 overrides and a sensible scoring function.
*Accept:* beats M0 in ≥80% of 200 local games; zero crashes; p99 latency < 20 ms.

**M2 — Feature layer + logging harness.**
`features.py` complete; self-play harness that records `(state, options, action, reward, next)`.
*Accept:* `test_no_leak` passes; 1,000 games logged; feature-dimension assertions hold.

**M3 — Behaviour cloning.**
`train_bc.py` on downloaded top-ladder replays.
*Accept:* top-1 agreement with expert action ≥45% on a held-out replay set; BC agent beats M1
baseline in ≥55% of games.

**M4 — Self-play DQN.**
`train_dqn.py`, initialised from M3, replay + target net + Double DQN.
*Accept:* ≥60% win rate vs M1 baseline over 500 games and no regression vs M3; loss curve
trends down and flattens; per-move p99 latency still within budget.

**M5 — Hybrid + ladder A/B.**
Q-net scores, rule-based overrides on top, lethal search, NumPy inference.
*Accept:* ladder μ above the M1 submission across at least 40 ladder games.

Do not skip M0–M2 to get to the neural network sooner. Every hour spent on a DQN that cannot
produce a valid submission is wasted.

---

## 11. Testing

- `pytest tests/` must be green before any submission is built.
- **Legality fuzz:** 500 games with a random opponent; assert zero exceptions and zero fallbacks
  triggered by bugs (fallbacks from genuine timeouts are logged separately).
- **Latency:** assert p99 decision time < 50% of the stated per-move limit.
- **Determinism:** same obs in, same action out, twice.
- **Bundle smoke test:** untar `submission.tar.gz` into a clean temp dir with no repo on the
  `PYTHONPATH` and run one full game. This catches the classic "works locally, imports `src/`,
  dies on the ladder" failure.

---

## 12. Known pitfalls, from prior sessions on this project

- **Deck format.** `deck.csv` must match `sample_submission` exactly — header row or not,
  quoting, one ID per row vs a count column, ID string format (leading zeros, prefixes). Copy the
  sample byte-for-byte and substitute IDs. Validate: exactly 60 entries, every ID present in
  `EN Card Data.csv`, ≤4 copies of any non-basic-Energy card name.
- **Card ID recognition.** IDs in the observation may be typed differently from the CSV (int vs
  string, zero-padded). Normalise once, in `features.py`, with an explicit `normalise_card_id()`
  and a startup assertion that every ID in `deck.csv` resolves in `card_features.npz`.
- **Multi-select contexts.** Some decisions want *several* indices (discard 2, choose 3 to shuffle
  back). Returning one index there is an illegal move. Handle each context kind explicitly and
  score the option *set*, greedily for v1.
- **The deck-selection context.** It returns 60 card IDs, not option indices — a completely
  different return type from the same function. It is easy to miss and it breaks game one.
- **Index vs identity.** Return positions in the legal-option list, not card IDs or internal
  action IDs, in all non-deck contexts.
- **Silent fallbacks.** If `_legal_fallback` is firing on 30% of decisions, the agent is a random
  bot with extra steps. Count and log fallback rate as a first-class metric.

---

## 13. Commands

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/pip install kaggle-environments==<pin_to_ladder_version>

venv/bin/pytest tests/ -q
venv/bin/python tools/evaluate.py --agent src.baseline --opponent random --games 200
venv/bin/python src/train_bc.py   --replays docs/official/replays --out ckpt/bc.pt
venv/bin/python src/train_dqn.py  --init ckpt/bc.pt --steps 500000 --out ckpt/dqn.pt
venv/bin/python src/export_weights.py --ckpt ckpt/dqn.pt --out weights.npz
venv/bin/python tools/build_submission.py --out submission.tar.gz
venv/bin/kaggle competitions submit pokemon-tcg-ai-battle -f submission.tar.gz -m "M4 dqn v1"
```

---

## 14. Definition of done

`submission.tar.gz` builds from a clean checkout, passes the bundle smoke test, plays 500 local
games with zero crashes and a fallback rate under 2%, holds p99 latency under half the move
budget, beats the rule-based baseline in ≥60% of games, and has a scored ladder submission whose
μ exceeds the baseline submission's.
