"""Train a learned reviewer on the recorded blocks.

One model per call, one process: a tiny GRU or a FastGRNN cell, of a chosen
width. Selected on the validation split's loss, then given a softmax
temperature fitted on that same split. The test split is not opened.

    PYTHONPATH="src:." python3 scripts/train_reviewer.py --kind gru --hidden 16

Writes the weights as an .npz that `evpil.control.tiny_rnn` runs without
torch, and a .json beside it with what the model scored on validation.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from evpil.control.supervisor import DIAGNOSES, FEATURES, N_FEATURES
from evpil.control.tiny_rnn import TinyReviewer

# Blocks per training sequence. A fault run is 430 blocks and its fault
# starts at block 300: a 300-block chunk would start every fault from an
# empty state, which is not how the model is run. 440 keeps a fault run whole.
CHUNK = 440


class FastGRNN(nn.Module):
    def __init__(self, n_in: int, hidden: int) -> None:
        super().__init__()
        self.w = nn.Parameter(torch.randn(hidden, n_in) * 0.1)
        self.u = nn.Parameter(torch.randn(hidden, hidden) * 0.1)
        self.b_z = nn.Parameter(torch.ones(hidden))
        self.b_h = nn.Parameter(torch.zeros(hidden))
        self.zeta = nn.Parameter(torch.ones(1))
        self.nu = nn.Parameter(-4.0 * torch.ones(1))
        self.hidden = hidden

    def forward(self, x):                       # (batch, time, n_in)
        h = x.new_zeros(x.shape[0], self.hidden)
        out = []
        zeta, nu = torch.sigmoid(self.zeta), torch.sigmoid(self.nu)
        for t in range(x.shape[1]):
            pre = x[:, t] @ self.w.T + h @ self.u.T
            z = torch.sigmoid(pre + self.b_z)
            c = torch.tanh(pre + self.b_h)
            h = (zeta * (1.0 - z) + nu) * c + z * h
            out.append(h)
        return torch.stack(out, dim=1)


class Net(nn.Module):
    def __init__(self, kind: str, hidden: int) -> None:
        super().__init__()
        self.kind = kind
        self.cell = (nn.GRU(N_FEATURES, hidden, batch_first=True)
                     if kind == "gru" else FastGRNN(N_FEATURES, hidden))
        self.out = nn.Linear(hidden, len(DIAGNOSES))

    def forward(self, x):
        h = self.cell(x)
        return self.out(h[0] if self.kind == "gru" else h)

    def export(self) -> dict:
        g = lambda t: t.detach().cpu().numpy().astype(np.float32)
        w = {"kind": self.kind, "w_out": g(self.out.weight),
             "b_out": g(self.out.bias)}
        if self.kind == "gru":
            c = self.cell
            w.update(w_ih=g(c.weight_ih_l0), w_hh=g(c.weight_hh_l0),
                     b_ih=g(c.bias_ih_l0), b_hh=g(c.bias_hh_l0))
        else:
            c = self.cell
            w.update(w=g(c.w), u=g(c.u), b_z=g(c.b_z), b_h=g(c.b_h),
                     zeta=g(c.zeta), nu=g(c.nu))
        return w


def chunks(d, chunk: int):
    """Cut each run into pieces of `chunk` blocks; a piece never spans two
    runs. Short tails are padded and masked."""
    xs, ys, ms = [], [], []
    at = 0
    for n in d["lens"]:
        for s in range(0, int(n), chunk):
            e = min(int(n), s + chunk)
            x = np.zeros((chunk, N_FEATURES), np.float32)
            y = np.zeros(chunk, np.int64)
            m = np.zeros(chunk, np.float32)
            x[:e - s], y[:e - s], m[:e - s] = (
                d["x"][at + s:at + e], d["y"][at + s:at + e], 1.0)
            xs.append(x), ys.append(y), ms.append(m)
        at += int(n)
    return (torch.tensor(np.array(xs)), torch.tensor(np.array(ys)),
            torch.tensor(np.array(ms)))


def run_whole(model: TinyReviewer, d) -> np.ndarray:
    """Logits for every block, each run from a fresh state: how the model
    is used in the loop."""
    out = np.zeros((len(d["y"]), len(DIAGNOSES)), np.float32)
    at = 0
    for n in d["lens"]:
        model.reset()
        for i in range(at, at + int(n)):
            out[i] = model.logits(d["x"][i])
        at += int(n)
    return out


def nll(logits: np.ndarray, y: np.ndarray, temp: float,
        sample_weight: np.ndarray | None = None) -> float:
    z = logits / temp
    z = z - z.max(axis=1, keepdims=True)
    logp = z - np.log(np.exp(z).sum(axis=1, keepdims=True))
    each = -logp[np.arange(len(y)), y]
    return float(each.mean() if sample_weight is None
                 else (each * sample_weight).mean())


def scores(logits: np.ndarray, y: np.ndarray, temp: float) -> dict:
    z = logits / temp
    z = z - z.max(axis=1, keepdims=True)
    p = np.exp(z)
    p /= p.sum(axis=1, keepdims=True)
    onehot = np.eye(len(DIAGNOSES))[y]
    pred = p.argmax(axis=1)
    conf = p.max(axis=1)
    bins = np.linspace(0.0, 1.0, 11)
    rel, ece = [], 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            acc, c = float((pred[m] == y[m]).mean()), float(conf[m].mean())
            rel.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(m.sum()),
                        "confidence": c, "accuracy": acc})
            ece += m.mean() * abs(acc - c)
    p_fault, is_fault = p[:, 1] + p[:, 3], (y % 2 == 1)
    return {
        "accuracy": float((pred == y).mean()),
        "nll": nll(logits, y, temp),
        "brier": float(((p - onehot) ** 2).sum(axis=1).mean()),
        "ece": float(ece), "reliability": rel,
        "recall_by_class": {DIAGNOSES[k]: float((pred[y == k] == k).mean())
                            for k in range(len(DIAGNOSES)) if (y == k).any()},
        "sensor_fault_brier": float(((p_fault - is_fault) ** 2).mean()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=("gru", "fastgrnn"))
    ap.add_argument("--hidden", type=int, default=16)
    ap.add_argument("--data", default="data/reviewer")
    ap.add_argument("--out", default="data/reviewer")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--weighting", default="sqrt", choices=("sqrt", "full"),
                    help="class weights: square root of inverse frequency, "
                         "or inverse frequency. With 'full' the model is "
                         "also selected on class-balanced validation loss")
    ap.add_argument("--weight-decay", type=float, default=0.0)
    ap.add_argument("--drop", default="",
                    help="comma-separated inputs to zero, e.g. v_meas,torque")
    ap.add_argument("--val", default=None,
                    help="validation blocks; default val.npz beside the "
                         "training data")
    ap.add_argument("--tag", default="",
                    help="suffix for the output file stem")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    torch.set_num_threads(2)
    tr = dict(np.load(f"{args.data}/train.npz"))
    va = dict(np.load(args.val or f"{args.data}/val.npz"))
    mask = np.array([0.0 if f in args.drop.split(",") else 1.0
                     for f in FEATURES], np.float32)
    tr["x"] = tr["x"] * mask
    x, y, m = chunks(tr, CHUNK)
    counts = np.bincount(tr["y"], minlength=len(DIAGNOSES)).astype(float)
    # Inverse-frequency weights, square-rooted: the healthy class is most of
    # the data, and full inverse weighting trades too much of it away.
    inv = counts.sum() / np.maximum(counts, 1.0)
    weight = torch.tensor(np.sqrt(inv) if args.weighting == "sqrt" else inv,
                          dtype=torch.float32)
    weight = weight / weight.mean()
    va_counts = np.bincount(va["y"], minlength=len(DIAGNOSES)).astype(float)
    va_w = (va_counts.sum() / np.maximum(va_counts, 1.0))[va["y"]]
    va_w = va_w / va_w.mean() if args.weighting == "full" else None

    net = Net(args.kind, args.hidden)
    opt = torch.optim.AdamW(net.parameters(), lr=3e-3,
                            weight_decay=args.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs)
    loss_fn = nn.CrossEntropyLoss(weight=weight, reduction="none")
    gen = torch.Generator().manual_seed(args.seed)
    best, best_w, history = float("inf"), None, []
    t0 = time.time()
    for epoch in range(args.epochs):
        net.train()
        order = torch.randperm(len(x), generator=gen)
        total = 0.0
        for i in range(0, len(order), 64):
            idx = order[i:i + 64]
            logits = net(x[idx])
            loss = (loss_fn(logits.reshape(-1, len(DIAGNOSES)),
                            y[idx].reshape(-1)) * m[idx].reshape(-1)).sum() \
                / m[idx].sum()
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            total += float(loss.detach()) * len(idx)
        sched.step()
        w = {**net.export(), "mask": mask}
        v = nll(run_whole(TinyReviewer(w), va), va["y"], 1.0, va_w)
        history.append({"epoch": epoch, "train_loss": total / len(x),
                        "val_nll": v})
        if v < best:
            best, best_w = v, w
        print(f"epoch {epoch:2d} train {total / len(x):.4f} val {v:.4f} "
              f"{time.time() - t0:4.0f} s", flush=True)

    model = TinyReviewer(best_w)
    logits = run_whole(model, va)
    temps = np.exp(np.linspace(np.log(0.5), np.log(5.0), 47))
    temp = float(temps[np.argmin([nll(logits, va["y"], t) for t in temps])])
    best_w["temperature"] = np.float32(temp)
    stem = f"{args.out}/{args.kind}{args.hidden}{args.tag}"
    np.savez(f"{stem}.npz", **best_w)
    report = {
        "kind": args.kind, "hidden": args.hidden, "seed": args.seed,
        "weighting": args.weighting, "weight_decay": args.weight_decay,
        "dropped_inputs": [f for f in args.drop.split(",") if f],
        "chunk_blocks": CHUNK,
        "train_data": args.data,
        "parameters": model.n_params(), "weight_bytes": model.weight_bytes(),
        "temperature": temp, "data_config": str(tr["config"]),
        "train_blocks": int(len(tr["y"])), "val_blocks": int(len(va["y"])),
        "validation_uncalibrated": scores(logits, va["y"], 1.0),
        "validation": scores(logits, va["y"], temp),
        "history": history,
    }
    Path(f"{stem}.json").write_text(json.dumps(report, indent=1) + "\n")
    v = report["validation"]
    print(f"{args.kind}{args.hidden}: {model.n_params()} parameters, "
          f"{model.weight_bytes()} bytes, T={temp:.2f}, accuracy "
          f"{v['accuracy']:.4f}, Brier {v['brier']:.4f}, ECE {v['ece']:.4f}, "
          f"recall {v['recall_by_class']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
