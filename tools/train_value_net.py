"""Step 3 (docs/writeup/ablation_log.md): train the value net on collected
self-play positions, hold out 20%, report held-out accuracy and calibration
before wiring it into anything.

Run with: python tools/train_value_net.py [data_path] [out_path]
"""

import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.value_net import train_value_net  # noqa: E402

N_CALIBRATION_BINS = 10


def calibration_report(probs: np.ndarray, y: np.ndarray) -> list[dict]:
    bins = np.linspace(0.0, 1.0, N_CALIBRATION_BINS + 1)
    rows = []
    for i in range(N_CALIBRATION_BINS):
        lo, hi = bins[i], bins[i + 1]
        mask = (probs >= lo) & (probs < hi) if i < N_CALIBRATION_BINS - 1 else (probs >= lo) & (probs <= hi)
        count = int(mask.sum())
        if count == 0:
            rows.append({"bin": f"[{lo:.1f},{hi:.1f})", "count": 0, "mean_pred": None, "actual_rate": None})
            continue
        rows.append({
            "bin": f"[{lo:.1f},{hi:.1f})",
            "count": count,
            "mean_pred": float(probs[mask].mean()),
            "actual_rate": float(y[mask].mean()),
        })
    return rows


def main() -> None:
    data_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_ROOT, "data", "value_net", "positions.npz")
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO_ROOT, "ckpt", "value_net.npz")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    data = np.load(data_path)
    X, y = data["X"], data["y"]
    game_ids = data["game_ids"]
    print(f"loaded {len(X)} positions, {y.mean():.3f} positive fraction")

    # Game-level split, not position-level: positions from the same game are
    # correlated (early-game features for a game player 0 goes on to win
    # aren't independent of that game's overall trajectory), so splitting
    # individual positions randomly would let the same game's positions
    # leak across train/val and inflate held-out accuracy. Held-out games
    # are entirely unseen during training.
    unique_games = np.unique(game_ids)
    rng = np.random.default_rng(0)
    shuffled_games = rng.permutation(unique_games)
    n_val_games = int(len(shuffled_games) * 0.2)
    val_games = set(shuffled_games[:n_val_games].tolist())
    val_mask = np.isin(game_ids, list(val_games))
    X_val, y_val = X[val_mask], y[val_mask]
    X_train, y_train = X[~val_mask], y[~val_mask]
    print(f"games: {len(unique_games)} total, {n_val_games} held out")
    print(f"train: {len(X_train)} positions  val (held out, game-level split): {len(X_val)} positions")

    net, history = train_value_net(X_train, y_train, X_val, y_val, epochs=60, batch_size=256, lr=1e-3, seed=0)

    val_probs = net.predict(X_val)
    val_acc = float(np.mean((val_probs >= 0.5) == (y_val >= 0.5)))
    val_probs_c = np.clip(val_probs, 1e-7, 1 - 1e-7)
    val_logloss = float(-np.mean(y_val * np.log(val_probs_c) + (1 - y_val) * np.log(1 - val_probs_c)))
    brier = float(np.mean((val_probs - y_val) ** 2))

    # Baseline for comparison: always predict the training-set base rate.
    base_rate = float(y_train.mean())
    baseline_acc = max(base_rate, 1 - base_rate)  # best a constant predictor can do at threshold 0.5
    baseline_brier = float(np.mean((base_rate - y_val) ** 2))

    print(f"\n=== Held-out results (n={len(X_val)}) ===")
    print(f"accuracy: {val_acc:.4f}  (constant-predictor baseline: {baseline_acc:.4f})")
    print(f"log loss: {val_logloss:.4f}")
    print(f"Brier score: {brier:.4f}  (constant-predictor baseline: {baseline_brier:.4f})")

    print(f"\n=== Calibration (held-out, {N_CALIBRATION_BINS} bins) ===")
    print(f"{'bin':<14}{'count':<8}{'mean_pred':<12}{'actual_rate':<12}")
    for row in calibration_report(val_probs, y_val):
        mp = f"{row['mean_pred']:.3f}" if row["mean_pred"] is not None else "-"
        ar = f"{row['actual_rate']:.3f}" if row["actual_rate"] is not None else "-"
        print(f"{row['bin']:<14}{row['count']:<8}{mp:<12}{ar:<12}")

    net.save(out_path)
    print(f"\nsaved to {out_path}")


if __name__ == "__main__":
    main()
