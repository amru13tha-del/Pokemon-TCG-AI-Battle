"""Step 3 value net (docs/writeup/ablation_log.md): a small MLP mapping
src/value_features.py's 17-dim position vector to a single scalar --
estimated win probability for the player to move. Pure NumPy for both
training and inference, deliberately -- matches src/baseline.py's
zero-extra-failure-surface philosophy (no PyTorch dependency reintroduced
after the DQN pipeline was removed).

Architecture: FEATURE_DIM -> 32 (ReLU) -> 16 (ReLU) -> 1 (sigmoid). Two
hidden layers, per the "2-3 hidden layers" spec. Manual backprop + Adam.
"""

import numpy as np

from src.value_features import FEATURE_DIM

HIDDEN1 = 32
HIDDEN2 = 16


def _relu(z: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, z)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


class ValueNet:
    def __init__(self, seed: int | None = None):
        rng = np.random.default_rng(seed)
        # He initialization for ReLU layers, Xavier-ish for the output layer.
        self.W1 = rng.normal(0, np.sqrt(2.0 / FEATURE_DIM), (FEATURE_DIM, HIDDEN1)).astype(np.float32)
        self.b1 = np.zeros(HIDDEN1, dtype=np.float32)
        self.W2 = rng.normal(0, np.sqrt(2.0 / HIDDEN1), (HIDDEN1, HIDDEN2)).astype(np.float32)
        self.b2 = np.zeros(HIDDEN2, dtype=np.float32)
        self.W3 = rng.normal(0, np.sqrt(1.0 / HIDDEN2), (HIDDEN2, 1)).astype(np.float32)
        self.b3 = np.zeros(1, dtype=np.float32)

    def forward(self, X: np.ndarray) -> dict:
        z1 = X @ self.W1 + self.b1
        a1 = _relu(z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = _relu(z2)
        z3 = a2 @ self.W3 + self.b3
        a3 = _sigmoid(z3)
        return {"z1": z1, "a1": a1, "z2": z2, "a2": a2, "z3": z3, "a3": a3}

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Win probability for the player-to-move, shape (N,)."""
        return self.forward(np.atleast_2d(X).astype(np.float32))["a3"].reshape(-1)

    def params(self) -> dict:
        return {"W1": self.W1, "b1": self.b1, "W2": self.W2, "b2": self.b2, "W3": self.W3, "b3": self.b3}

    def save(self, path: str) -> None:
        np.savez(path, **self.params())

    @classmethod
    def load(cls, path: str) -> "ValueNet":
        data = np.load(path)
        net = cls.__new__(cls)
        for k in ("W1", "b1", "W2", "b2", "W3", "b3"):
            setattr(net, k, data[k])
        return net


def _adam_init(params: dict) -> dict:
    return {k: {"m": np.zeros_like(v), "v": np.zeros_like(v)} for k, v in params.items()}


def train_value_net(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 60,
    batch_size: int = 256,
    lr: float = 1e-3,
    seed: int = 0,
    verbose: bool = True,
    patience: int = 8,
) -> tuple[ValueNet, list[dict]]:
    """Trains in place via manual backprop + Adam, with early stopping on
    val_loss (best-weights restored) -- the game-level held-out split
    diverges train/val loss after ~10 epochs on this dataset, so training
    for a fixed epoch count without early stopping overfits and produces a
    less honest held-out number. Returns (net, history) -- history is a
    list of per-epoch {epoch, train_loss, val_loss, val_acc}."""
    net = ValueNet(seed=seed)
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    adam = _adam_init(net.params())
    t = 0
    rng = np.random.default_rng(seed)
    n = X_train.shape[0]
    history = []
    best_val_loss = float("inf")
    best_params = None
    epochs_without_improvement = 0

    for epoch in range(epochs):
        perm = rng.permutation(n)
        X_shuf, y_shuf = X_train[perm], y_train[perm]
        epoch_loss = 0.0
        for start in range(0, n, batch_size):
            xb = X_shuf[start:start + batch_size]
            yb = y_shuf[start:start + batch_size].reshape(-1, 1)
            m = xb.shape[0]

            cache = net.forward(xb)
            a1, a2, a3 = cache["a1"], cache["a2"], cache["a3"]
            eps_clip = 1e-7
            a3c = np.clip(a3, eps_clip, 1 - eps_clip)
            batch_loss = -np.mean(yb * np.log(a3c) + (1 - yb) * np.log(1 - a3c))
            epoch_loss += batch_loss * m

            dz3 = (a3 - yb) / m
            dW3 = a2.T @ dz3
            db3 = dz3.sum(axis=0)
            da2 = dz3 @ net.W3.T
            dz2 = da2 * (cache["z2"] > 0)
            dW2 = a1.T @ dz2
            db2 = dz2.sum(axis=0)
            da1 = dz2 @ net.W2.T
            dz1 = da1 * (cache["z1"] > 0)
            dW1 = xb.T @ dz1
            db1 = dz1.sum(axis=0)

            grads = {"W1": dW1, "b1": db1, "W2": dW2, "b2": db2, "W3": dW3, "b3": db3}
            t += 1
            for k, g in grads.items():
                state = adam[k]
                state["m"] = beta1 * state["m"] + (1 - beta1) * g
                state["v"] = beta2 * state["v"] + (1 - beta2) * (g ** 2)
                m_hat = state["m"] / (1 - beta1 ** t)
                v_hat = state["v"] / (1 - beta2 ** t)
                update = lr * m_hat / (np.sqrt(v_hat) + eps)
                setattr(net, k, getattr(net, k) - update)

        train_loss = epoch_loss / n
        val_probs = net.predict(X_val)
        val_probs_c = np.clip(val_probs, 1e-7, 1 - 1e-7)
        val_loss = -np.mean(y_val * np.log(val_probs_c) + (1 - y_val) * np.log(1 - val_probs_c))
        val_acc = float(np.mean((val_probs >= 0.5) == (y_val >= 0.5)))
        history.append({"epoch": epoch, "train_loss": float(train_loss), "val_loss": float(val_loss), "val_acc": val_acc})
        if verbose and (epoch % 5 == 0 or epoch == epochs - 1):
            print(f"  epoch {epoch:3d}  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  val_acc={val_acc:.4f}")

        if val_loss < best_val_loss - 1e-5:
            best_val_loss = val_loss
            best_params = {k: v.copy() for k, v in net.params().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                if verbose:
                    print(f"  early stopping at epoch {epoch} (no val_loss improvement for {patience} epochs)")
                break

    if best_params is not None:
        for k, v in best_params.items():
            setattr(net, k, v)
    return net, history
