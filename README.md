# Pokemon TCG AI Battle

An agent for *The Pokémon Company — PTCG AI Battle Challenge* on Kaggle
(Simulation track: `pokemon-tcg-ai-battle`; Strategy track:
`pokemon-tcg-ai-battle-challenge-strategy`).

## What's here

- `main.py` — the submission entry point: `agent(obs_dict) -> list[int]`,
  wrapped so it never raises and always returns a legal action.
- `src/baseline.py` — the active agent (M1): a rule-based policy (hard
  overrides for lethal/trade-up/safe-retreat decisions, plus a
  context-scoring heuristic for everything else). Every rule is cited
  against the engine's own source in a `RULES` dict at the top of the file.
- `src/value_features.py`, `src/switch_predict.py`, `src/value_net.py` —
  a small NumPy value network built to help retreat-target scoring,
  validated end-to-end but ultimately not adopted (see below).
- `tests/` — regression tests, run as plain scripts
  (`python tests/test_legality.py [n_games]`), not pytest.
- `tools/` — evaluation (`evaluate.py`) and submission packaging
  (`build_submission.py`).
- `docs/writeup/` — the full experimental record: `ablation_log.md` (six
  single-change candidates tested against a frozen control, all six
  rejected, each with a logged root cause or noise analysis), `outline.md`
  (the Strategy Writeup draft), and `figures/` (Media Gallery charts built
  from the logged numbers).

## What this agent is

A rule-based policy, not a trained model. An earlier attempt built a full
RL pipeline (DQN + behaviour cloning); it was deliberately deleted in
favor of a disciplined, single-change ablation process against a frozen
control baseline. A later attempt added a small supervised value network
for one specific decision type (retreat-target scoring) — it was validated
at every stage (including catching and fixing a real data-leakage bug
before trusting its own accuracy number) but didn't beat the rule-based
control on win rate at any tested blend weight, so it was reverted. Both
episodes are documented in full in `docs/writeup/ablation_log.md`, not
quietly dropped.

## Running this yourself

This repo does **not** include the competition's battle engine (`cg/`) or
its card database (`docs/official/`). Those are licensed to competition
entrants only — the engine's own license says "please don't redistribute
it, post it publicly... any copy or adaptation of it shall be deemed
'Pokémon Elements'" (see the Competition Rules on the Kaggle page). If
you're entering this competition yourself, get `cg/` from the official
Kaggle competition page and drop it in at the repo root; everything else
here should then run as-is.

```
python tests/test_legality.py 30
python tools/evaluate.py --agent src.baseline --opponent random --games 200
```
