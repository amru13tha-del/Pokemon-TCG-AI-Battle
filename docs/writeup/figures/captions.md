# Media Gallery captions

One to two sentences per figure, each under 40 words, stating the claim the
figure supports. Source data: `docs/writeup/ablation_log.md`, `deck.csv`,
and a live `kaggle competitions submissions` check — see
`build_figures.py`'s inline comments for the exact source of every number.

## ablation.png (37 words)

All six single-change scoring candidates were rejected against a frozen
control (n=300 each): one is a root-caused regression, one is a proven
no-op, the rest fall inside the noise band shown. None cleared the 53%
acceptance bar.

## ladder.png (28 words)

Live Kaggle public scores for the three completed submissions, checked via
the Kaggle API. Ratings update continuously as ladder games play out —
these are not final numbers.

## local_vs_ladder.png (33 words)

The two variants with both metrics: nearly identical local win rates
(91.5% vs. 88.5%) produced a ~219-point live-ladder gap. Only 2 data
points exist — this is the complete set, not a sample.

## valuenet.png (34 words)

The value net showed a real, validated signal in isolation (62.3%
held-out accuracy vs. 51.6% baseline), but blending it into scoring never
beat control at any of 5 weights tested — all within noise.

## deck.png (27 words)

60 cards: 12 all-Basic single-prize attackers, 32 Trainers (mostly
search/draw), 16 Fighting Energy. All-Basic removes any need for
multi-turn evolution planning the greedy per-turn policy can't do.

---

## Data quality flags — for you to decide on

- **local_vs_ladder.png has only 2 real data points.** M0 has no local
  win-rate metric comparable to M1/M1+deck (it was only ever tested for
  legality, not win rate, so it can't be plotted without inventing a
  number — not done here). The ablation candidates and the value-net
  blend sweep all have local win rates but were never submitted to the
  ladder, so they have no live-score value either. This figure is real
  and not misleading, but it is definitionally a 2-point figure, not a
  distribution — decide whether that's acceptable for the gallery or
  whether it needs a different framing (e.g., a paired bar/table instead
  of a scatter, which might read less like an implied trend).
- **No per-epoch training curve exists in the repo for the value net** —
  only final metrics were ever saved to a file (`ablation_log.md`); the
  epoch-by-epoch trajectory shown live during training was never
  persisted. `valuenet.png` uses only the final, saved numbers (held-out
  accuracy and the blend sweep) — it does not and cannot show a training
  curve, since that data doesn't exist in the repo per the hard rule
  against inventing it.
- **Deck trainer count corrected.** The task brief said 28 Trainers;
  `deck.csv` actually has 32 (12 Pokémon + 32 Trainers + 16 Energy = 60,
  which is the only combination that sums correctly). `deck.png` uses the
  verified 32.
