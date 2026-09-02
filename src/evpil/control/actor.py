"""Export a trained SAC actor, cost it, and run it without PyTorch.

Three jobs, all of them about the same thing: the policy that gets reported
has to be the policy that runs on the device.

  1. Pull the actor's weights out of the Stable-Baselines3 policy into plain
     arrays. The critic is training scaffolding and does not ship.
  2. Evaluate it in numpy, so the host-side evaluation and the C
     implementation share one reference that is not PyTorch.
  3. Cost it against the G5 budget at the moment it is trained, not at the
     deployment gate. That rule was written after the forecasting ladder
     produced a best model that did not fit.

Deterministic action is `tanh(mu(h))`. SAC's actor outputs the mean and log
standard deviation of a squashed Gaussian; at evaluation time the standard
deviation is unused and the mean is squashed through tanh. Sampling is a
training-time behaviour and there is no reason to ship a random number
generator to a microcontroller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Measured on the S3 at gate G1: a scalar int8 multiply-accumulate loop at
# 240 MHz on one core. Used here only to rank and to sanity-check; week 6
# established that a MAC count is not a latency, so the number that gets
# reported is the one measured on silicon.
G1_MMAC_PER_S = 29.82
G5_LATENCY_BUDGET_MS = 40.0
G5_FOOTPRINT_BUDGET_KB = 300.0


@dataclass(frozen=True)
class Actor:
    """A plain multilayer perceptron with tanh-squashed outputs."""
    weights: list[np.ndarray]        # (out, in) per layer, PyTorch convention
    biases: list[np.ndarray]
    obs_scale: np.ndarray
    obs_clip: float
    action_low: np.ndarray
    action_high: np.ndarray

    @property
    def layer_sizes(self) -> list[int]:
        return [self.weights[0].shape[1]] + [w.shape[0] for w in self.weights]

    @property
    def n_params(self) -> int:
        return sum(w.size for w in self.weights) + sum(b.size for b in self.biases)

    @property
    def macs(self) -> int:
        return sum(int(w.size) for w in self.weights)

    def forward(self, obs_scaled: np.ndarray) -> np.ndarray:
        """Deterministic action in [-1, 1] from an already-scaled observation."""
        h = np.asarray(obs_scaled, dtype=np.float64)
        for w, b in zip(self.weights[:-1], self.biases[:-1]):
            h = np.maximum(h @ w.T + b, 0.0)          # ReLU
        return np.tanh(h @ self.weights[-1].T + self.biases[-1])

    def cost(self, *, int8: bool = False) -> dict:
        """Footprint and an estimated latency, both against the G5 budget.

        The latency is an estimate and is labelled as one. The measured figure
        comes from `firmware/main/bench_actor.c` running the same graph on the
        board, and it is the measured figure that goes in a results table.
        """
        bytes_per = 1 if int8 else 4
        footprint_kb = self.n_params * bytes_per / 1024.0
        est_ms = self.macs / (G1_MMAC_PER_S * 1e6) * 1e3
        return {
            "layer_sizes": self.layer_sizes,
            "n_params": self.n_params,
            "macs": self.macs,
            "dtype": "int8" if int8 else "float32",
            "footprint_kb": footprint_kb,
            "estimated_latency_ms": est_ms,
            "fits_footprint": footprint_kb <= G5_FOOTPRINT_BUDGET_KB,
            "fits_latency_estimate": est_ms <= G5_LATENCY_BUDGET_MS,
        }

    def save(self, path: str | Path) -> None:
        np.savez(
            path,
            n_layers=np.array([len(self.weights)]),
            obs_scale=self.obs_scale, obs_clip=np.array([self.obs_clip]),
            action_low=self.action_low, action_high=self.action_high,
            **{f"w{i}": w for i, w in enumerate(self.weights)},
            **{f"b{i}": b for i, b in enumerate(self.biases)},
        )

    @classmethod
    def load(cls, path: str | Path) -> "Actor":
        with np.load(path) as z:
            n = int(z["n_layers"][0])
            return cls(
                weights=[z[f"w{i}"] for i in range(n)],
                biases=[z[f"b{i}"] for i in range(n)],
                obs_scale=z["obs_scale"], obs_clip=float(z["obs_clip"][0]),
                action_low=z["action_low"], action_high=z["action_high"],
            )


def from_sb3(model) -> Actor:
    """Extract the actor from a trained SB3 SAC model.

    Reads the module list rather than assuming a shape, so a change of
    `net_arch` does not silently export the wrong graph.
    """
    import torch
    from torch import nn

    from evpil.control.env import OBS_CLIP, OBS_SCALE

    actor = model.policy.actor
    linears: list[nn.Linear] = [m for m in actor.latent_pi.modules()
                                if isinstance(m, nn.Linear)]
    linears.append(actor.mu)

    weights, biases = [], []
    for layer in linears:
        weights.append(layer.weight.detach().cpu().numpy().astype(np.float32))
        biases.append(layer.bias.detach().cpu().numpy().astype(np.float32))

    space = model.action_space
    return Actor(
        weights=weights, biases=biases,
        obs_scale=np.asarray(OBS_SCALE, dtype=np.float32),
        obs_clip=float(OBS_CLIP),
        action_low=np.asarray(space.low, dtype=np.float32),
        action_high=np.asarray(space.high, dtype=np.float32),
    )


def _c_float(v: float) -> str:
    """A C float literal that is always a float.

    `f"{10.0:.8g}"` is "10", and "10f" is not valid C -- the suffix needs a
    decimal point or an exponent in front of it. Every round weight in the
    network hits this, so it is worth a function rather than a hope.
    """
    text = f"{float(v):.8g}"
    if not any(c in text for c in ".eE"):
        text += ".0"
    return text + "f"


def write_c_header(actor: Actor, path: str | Path, name: str = "sac_actor",
                   *, p_limit_hi_w: float) -> None:
    """Emit the weights as a C header the firmware compiles in.

    Generated rather than hand-copied, and the generator is the only writer:
    a header edited by hand is a policy nobody trained.

    The action-decode bounds are emitted with the weights rather than left to
    the firmware to define, for the same reason. A policy whose outputs are
    decoded against different bounds is a different controller, and it fails
    silently: every number stays in range and the energy result is merely
    wrong. `p_limit_hi_w` is the vehicle's maximum motor power, which is the
    only one of the three that is a property of the car rather than of the
    action space; passing None omits the decode block, for a caller that only
    wants weights.
    """
    lines = [
        "/* Generated by evpil.control.actor.write_c_header. Do not edit. */",
        "#pragma once",
        "#include <stdint.h>",
        "",
        f"#define {name.upper()}_N_LAYERS {len(actor.weights)}",
    ]
    sizes = actor.layer_sizes
    lines.append(f"#define {name.upper()}_N_IN  {sizes[0]}")
    lines.append(f"#define {name.upper()}_N_OUT {sizes[-1]}")
    lines.append(f"#define {name.upper()}_MAX_WIDTH {max(sizes)}")
    lines.append("")
    lines.append(f"static const int {name}_sizes[{len(sizes)}] = {{"
                 + ", ".join(str(s) for s in sizes) + "};")
    lines.append("")

    def emit(arr: np.ndarray, label: str) -> None:
        flat = np.asarray(arr, dtype=np.float32).reshape(-1)
        lines.append(f"static const float {label}[{flat.size}] = {{")
        for i in range(0, flat.size, 8):
            chunk = ", ".join(_c_float(v) for v in flat[i:i + 8])
            lines.append("    " + chunk + ",")
        lines.append("};")
        lines.append("")

    for i, (w, b) in enumerate(zip(actor.weights, actor.biases)):
        emit(w, f"{name}_w{i}")            # row-major (out, in)
        emit(b, f"{name}_b{i}")
    emit(actor.obs_scale, f"{name}_obs_scale")
    lines.append(f"static const float {name}_obs_clip = "
                 f"{_c_float(actor.obs_clip)};")
    lines.append("")
    from evpil.control.env import DERATE_MAX, P_LIMIT_LO_W
    lines.append("/* Action decode, mirroring "
                 "EnergyManagementEnv.decode_action. */")
    lines.append(f"static const float {name}_p_limit_lo_w = "
                 f"{_c_float(P_LIMIT_LO_W)};")
    lines.append(f"static const float {name}_p_limit_hi_w = "
                 f"{_c_float(p_limit_hi_w)};")
    lines.append(f"static const float {name}_derate_max = "
                 f"{_c_float(DERATE_MAX)};")
    lines.append("")
    # Identifies which weights a binary was compiled against. Without it,
    # "the harness picked up a different header" is invisible: both networks
    # have the same shape, run without error, and disagree only in the
    # numbers, which is exactly the failure this whole file exists to prevent.
    lines.append(f"#define {name.upper()}_CHECKSUM 0x{actor_checksum(actor):08X}u")
    lines.append("")

    Path(path).write_text("\n".join(lines))


def actor_checksum(actor: Actor) -> int:
    """A stable 32-bit digest of the weights, biases and observation scale."""
    import zlib

    crc = 0
    for arr in [*actor.weights, *actor.biases, actor.obs_scale]:
        crc = zlib.crc32(np.ascontiguousarray(arr, dtype=np.float32).tobytes(),
                         crc)
    return crc & 0xFFFFFFFF


def summarise(actor: Actor) -> str:
    c = actor.cost()
    return (f"actor {'-'.join(str(s) for s in actor.layer_sizes)}: "
            f"{c['n_params']:,} parameters, {c['macs']:,} MACs, "
            f"{c['footprint_kb']:.1f} KB float32, "
            f"{c['estimated_latency_ms']:.3f} ms estimated")
