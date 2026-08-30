"""The forecasting arms of spec 4.2, behind one interface.

Every arm is a function from `(X_train, Y_train, X_eval)` to predictions for
`X_eval`, shaped `(n_eval, horizon)`. Nothing here holds state between calls and
nothing here reads a split it was not handed, which is what keeps the leakage
guards meaningful after training starts rather than only before it.

Two arms take the evaluation targets as a separate argument, for early stopping
only. Spec 5.2 permits that on the validation split and forbids it on test; the
argument is named `Y_stop` so that a call which passes test targets is visible
in the diff rather than buried in a keyword.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Standardiser:
    """Per-channel mean and standard deviation, fitted on training windows only.

    Fitting scaling statistics on the pooled dataset is the quietest form of
    leakage there is: it never shows up as a suspicious feature name, and it
    moves every reported number by a little.
    """

    mu: np.ndarray
    sd: np.ndarray

    @classmethod
    def fit(cls, X: np.ndarray) -> Standardiser:
        flat = X.reshape(-1, X.shape[-1]).astype(np.float64)
        sd = flat.std(axis=0)
        return cls(mu=flat.mean(axis=0), sd=np.where(sd > 0.0, sd, 1.0))

    def transform(self, X: np.ndarray) -> np.ndarray:
        return ((X - self.mu) / self.sd).astype(np.float32)


@dataclass(frozen=True)
class ArmResult:
    """Predictions plus whatever the arm can say about how it got there."""

    pred: np.ndarray
    n_params: int
    info: dict


def fit_ridge(
    X_tr: np.ndarray, Y_tr: np.ndarray, X_ev: np.ndarray, lam: float = 1.0
) -> ArmResult:
    """Least squares with a small ridge on flattened windows.

    The cheap arm that the rest of the ladder has to justify itself against.
    One factorisation serves all horizon steps.
    """
    scaler = Standardiser.fit(X_tr)
    A = scaler.transform(X_tr).reshape(len(X_tr), -1).astype(np.float64)
    B = scaler.transform(X_ev).reshape(len(X_ev), -1).astype(np.float64)
    A = np.hstack([A, np.ones((len(A), 1))])
    B = np.hstack([B, np.ones((len(B), 1))])

    Y = np.asarray(Y_tr, dtype=np.float64)
    G = A.T @ A + lam * np.eye(A.shape[1])
    W = np.linalg.solve(G, A.T @ Y)
    return ArmResult(pred=B @ W, n_params=int(W.size), info={"lambda": lam})


def fit_xgboost(
    X_tr: np.ndarray,
    Y_tr: np.ndarray,
    X_ev: np.ndarray,
    Y_stop: np.ndarray,
    *,
    max_depth: int = 4,
    learning_rate: float = 0.05,
    n_estimators: int = 2000,
    early_stopping_rounds: int = 50,
    min_child_weight: float = 20.0,
    reg_lambda: float = 5.0,
    subsample: float = 0.8,
    colsample_bytree: float = 0.6,
    seed: int = 0,
) -> ArmResult:
    """One booster per horizon step, on flattened windows.

    Per step rather than a single vector-leaf model because the horizon steps
    are different problems: 0.1 s ahead is nearly determined by the last sample
    and 3.0 s ahead is not, and one shared tree structure would have to
    compromise between them.

    `Y_stop` is used for early stopping only, which spec 5.2 permits on
    validation.
    """
    import xgboost as xgb

    A = X_tr.reshape(len(X_tr), -1)
    B = X_ev.reshape(len(X_ev), -1)
    horizon = Y_tr.shape[1]

    pred = np.empty((len(B), horizon), dtype=np.float64)
    rounds, n_trees = [], 0
    for h in range(horizon):
        model = xgb.XGBRegressor(
            max_depth=max_depth, learning_rate=learning_rate,
            n_estimators=n_estimators, min_child_weight=min_child_weight,
            reg_lambda=reg_lambda, subsample=subsample,
            colsample_bytree=colsample_bytree, tree_method="hist",
            early_stopping_rounds=early_stopping_rounds, n_jobs=-1,
            random_state=seed,
        )
        model.fit(A, Y_tr[:, h], eval_set=[(B, Y_stop[:, h])], verbose=False)
        pred[:, h] = model.predict(B)
        rounds.append(int(model.best_iteration))
        n_trees += int(model.best_iteration) + 1

    return ArmResult(
        pred=pred,
        n_params=n_trees,  # trees, not weights; see the report
        info={"best_rounds": rounds, "max_depth": max_depth,
              "learning_rate": learning_rate, "seed": seed},
    )


def fit_lstm(
    X_tr: np.ndarray,
    Y_tr: np.ndarray,
    X_ev: np.ndarray,
    Y_stop: np.ndarray,
    *,
    hidden: int = 64,
    layers: int = 1,
    epochs: int = 12,
    batch_size: int = 256,
    lr: float = 1e-3,
    seed: int = 0,
    device: str | None = None,
    cpu_threads: int | None = 1,
) -> ArmResult:
    """An LSTM on real `(batch, seq_len, features)` tensors.

    This arm exists to settle defect D4. The predecessor work reshaped its data
    to `(n, n_features)` and called the result a sequence, so its LSTM saw one
    timestep and unsurprisingly lost to everything. Here the recurrence runs
    over the 32 input samples, and whatever the arm scores is a property of the
    model rather than of a reshape.

    The returned predictions are from the epoch with the lowest validation
    RMSE, pooled over the horizon. Selecting an epoch on validation is early
    stopping, which spec 5.2 permits; the test split is not touched.

    `cpu_threads` defaults to 1 and is not cosmetic. On macOS, XGBoost and
    PyTorch each load their own OpenMP runtime, and an LSTM forward pass large
    enough to take the parallel path deadlocks in a process where XGBoost has
    already fitted. Since the ladder runs both arms in one process, this is
    reached in normal use rather than only in a corner case. One thread costs
    little here -- the batches are small and MPS carries the real work when it
    is available -- and the setting is process-global and deliberately not
    restored afterwards, because restoring it would re-arm the deadlock for the
    next caller. Pass None to leave the thread count alone.
    """
    from evpil.forecast._openmp import ensure_import_order

    ensure_import_order()

    import torch
    from torch import nn

    if cpu_threads is not None:
        torch.set_num_threads(cpu_threads)

    if device is None:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    dev = torch.device(device)
    torch.manual_seed(seed)

    scaler = Standardiser.fit(X_tr)
    y_mu = float(Y_tr.mean())
    y_sd = float(Y_tr.std()) or 1.0

    Xt = torch.from_numpy(scaler.transform(X_tr))
    Yt = torch.from_numpy(((Y_tr - y_mu) / y_sd).astype(np.float32))
    Xv = torch.from_numpy(scaler.transform(X_ev)).to(dev)

    class Net(nn.Module):
        def __init__(self, n_feat: int, horizon: int) -> None:
            super().__init__()
            self.rnn = nn.LSTM(n_feat, hidden, layers, batch_first=True)
            self.head = nn.Linear(hidden, horizon)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            out, _ = self.rnn(x)
            return self.head(out[:, -1])

    net = Net(X_tr.shape[2], Y_tr.shape[1]).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(Xt, Yt), batch_size=batch_size, shuffle=True
    )

    best_rmse, best_pred, best_epoch, curve = np.inf, None, -1, []
    for epoch in range(epochs):
        net.train()
        for xb, yb in loader:
            xb, yb = xb.to(dev), yb.to(dev)
            opt.zero_grad()
            nn.functional.mse_loss(net(xb), yb).backward()
            opt.step()

        net.eval()
        with torch.no_grad():
            pred = net(Xv).cpu().numpy().astype(np.float64) * y_sd + y_mu
        rmse = float(np.sqrt(((pred - Y_stop) ** 2).mean()))
        curve.append(rmse)
        if rmse < best_rmse:
            best_rmse, best_pred, best_epoch = rmse, pred, epoch

    n_params = int(sum(p.numel() for p in net.parameters()))
    return ArmResult(
        pred=best_pred,
        n_params=n_params,
        info={"best_epoch": best_epoch, "val_rmse_curve": curve,
              "hidden": hidden, "layers": layers, "seed": seed, "device": device},
    )
