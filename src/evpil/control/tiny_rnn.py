"""The learned reviewers: a tiny GRU and a FastGRNN cell, run in numpy.

Training is in `scripts/train_reviewer.py`, with torch. What runs in the
loop is this file: one cell step per 100 ms block, float32, no torch, written
the way the C port will be so that the two can be compared number for number.

Both take the twelve block features of `evpil.control.supervisor` and give a
probability for each of its four diagnoses.

  GRU       r, z, n gates as torch.nn.GRU defines them
  FastGRNN  Kusupati et al. 2018: one shared pair of matrices for the gate
            and the candidate, and two learned scalars
              z  = sigmoid(W x + U h + b_z)
              h~ = tanh(W x + U h + b_h)
              h  = (zeta (1 - z) + nu) h~ + z h
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

F32 = np.float32


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class TinyReviewer:
    """A recurrent cell, a linear read-out, a softmax with a temperature
    fitted on held-out data."""

    def __init__(self, weights: dict, name: str | None = None) -> None:
        self.w = {k: np.asarray(v, dtype=F32) for k, v in weights.items()
                  if k not in ("kind", "temperature")}
        self.kind = str(weights["kind"])
        self.temperature = float(weights.get("temperature", 1.0))
        self.hidden = self.w["w_out"].shape[1]
        self.name = name or f"{self.kind}{self.hidden}"
        self.reset()

    @classmethod
    def load(cls, path: Path | str, name: str | None = None) -> "TinyReviewer":
        with np.load(path, allow_pickle=False) as z:
            return cls({k: z[k] for k in z.files}, name)

    def reset(self) -> None:
        self.h = np.zeros(self.hidden, dtype=F32)

    def n_params(self) -> int:
        return int(sum(v.size for v in self.w.values()))

    def weight_bytes(self) -> int:
        return 4 * self.n_params()

    def cell(self, x: np.ndarray) -> np.ndarray:
        w, h, n = self.w, self.h, self.hidden
        if self.kind == "gru":
            gi = w["w_ih"] @ x + w["b_ih"]
            gh = w["w_hh"] @ h + w["b_hh"]
            r = _sigmoid(gi[:n] + gh[:n])
            z = _sigmoid(gi[n:2 * n] + gh[n:2 * n])
            c = np.tanh(gi[2 * n:] + r * gh[2 * n:])
            self.h = ((1.0 - z) * c + z * h).astype(F32)
        elif self.kind == "fastgrnn":
            pre = w["w"] @ x + w["u"] @ h
            z = _sigmoid(pre + w["b_z"])
            c = np.tanh(pre + w["b_h"])
            zeta, nu = _sigmoid(w["zeta"][0]), _sigmoid(w["nu"][0])
            self.h = ((zeta * (1.0 - z) + nu) * c + z * h).astype(F32)
        else:
            raise ValueError(self.kind)
        return self.h

    def logits(self, x) -> np.ndarray:
        h = self.cell(np.asarray(x, dtype=F32))
        return self.w["w_out"] @ h + self.w["b_out"]

    def review(self, snap) -> tuple[float, ...]:
        z = self.logits(snap.x) / self.temperature
        z = z - z.max()
        p = np.exp(z)
        return tuple(float(v) for v in p / p.sum())
