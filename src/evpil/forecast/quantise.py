"""Post-training int8 quantisation, and what it costs in accuracy.

Ablation A2 asks for the accuracy of the same model at float32 and at int8.
The spec's deployment path is PyTorch to ONNX to TFLite to esp-tflite-micro,
and that toolchain is not installed here, so this module measures the
quantisation itself rather than the converter.

That is a real distinction and the report has to keep it. What is measured here
is the arithmetic: every weight and every activation is rounded to the values
an 8-bit tensor can hold, and the model is scored on those values. What is not
measured here is the converter's own choices, its operator fusions, or the
runtime's kernels. Those change latency and can change accuracy slightly. This
gives the accuracy cost of 8-bit arithmetic, which is the part that decides
whether deployment is worth attempting at all.

The method is fake quantisation: quantise to the integer grid and immediately
scale back to float, so the network computes in float over exactly the values
int8 can represent. It is the standard way to measure post-training
quantisation error, and it reproduces the integer result whenever the
accumulator does not overflow, which for these shapes it does not.

**Calibration uses training windows only.** A calibration set drawn from
validation or test data is a quiet leak: it lets the deployed model's numeric
ranges be chosen using data it is about to be scored on. `calibrate` takes the
split it was given and `tests/forecast/test_quantise.py` checks the caller
cannot pass evaluation data by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

INT8_MIN, INT8_MAX = -128, 127


@dataclass(frozen=True)
class QuantRange:
    """One tensor's quantisation grid.

    Symmetric for weights, because a symmetric grid needs no zero-point in the
    accumulator and that is what the device's kernels expect. Asymmetric for
    activations, because activations after a normalisation layer are not
    centred on zero and forcing a symmetric grid on them throws away half the
    codes.
    """

    scale: float
    zero_point: int
    symmetric: bool

    @classmethod
    def symmetric_from(cls, values: np.ndarray) -> QuantRange:
        peak = float(np.max(np.abs(values)))
        scale = peak / INT8_MAX if peak > 0.0 else 1.0
        return cls(scale=scale, zero_point=0, symmetric=True)

    @classmethod
    def affine_from(cls, lo: float, hi: float) -> QuantRange:
        # Include zero in the range: padding and residual paths produce exact
        # zeros, and a grid that cannot represent zero adds a bias everywhere
        # one appears.
        lo, hi = min(lo, 0.0), max(hi, 0.0)
        span = hi - lo
        if span <= 0.0:
            return cls(scale=1.0, zero_point=0, symmetric=False)
        scale = span / (INT8_MAX - INT8_MIN)
        zero_point = int(round(INT8_MIN - lo / scale))
        return cls(scale=scale,
                   zero_point=int(np.clip(zero_point, INT8_MIN, INT8_MAX)),
                   symmetric=False)

    def quantise(self, values):
        q = np.round(values / self.scale) + self.zero_point
        return np.clip(q, INT8_MIN, INT8_MAX)

    def dequantise(self, codes):
        return (codes - self.zero_point) * self.scale

    def fake_quantise(self, values):
        """Round to the int8 grid and return to float, as the device would see it."""
        return self.dequantise(self.quantise(values))


@dataclass
class ActivationObserver:
    """Running min and max of a tensor, for activation calibration."""

    lo: float = np.inf
    hi: float = -np.inf
    n_seen: int = 0

    def observe(self, values) -> None:
        arr = np.asarray(values, dtype=np.float64)
        self.lo = min(self.lo, float(arr.min()))
        self.hi = max(self.hi, float(arr.max()))
        self.n_seen += len(arr)

    def to_range(self) -> QuantRange:
        if self.n_seen == 0:
            raise ValueError(
                "no data observed. An uncalibrated activation range would be "
                "invented rather than measured."
            )
        return QuantRange.affine_from(self.lo, self.hi)


def quantise_weights(state: dict) -> tuple[dict, dict]:
    """Fake-quantise every weight tensor. Biases are left alone.

    Biases stay in higher precision on the device too: they are added into a
    32-bit accumulator, so rounding them to 8 bits would throw away accuracy
    for no memory saving worth having.
    """
    out, ranges = {}, {}
    for name, tensor in state.items():
        values = np.asarray(tensor, dtype=np.float64)
        if name.endswith("bias") or values.ndim < 2:
            out[name] = values
            continue
        rng = QuantRange.symmetric_from(values)
        ranges[name] = rng
        out[name] = rng.fake_quantise(values)
    return out, ranges


def weight_bytes(state: dict) -> int:
    """Bytes the weights occupy once quantised: one per element, four per bias."""
    total = 0
    for name, tensor in state.items():
        values = np.asarray(tensor)
        total += values.size * (4 if (name.endswith("bias") or values.ndim < 2)
                                else 1)
    return total


def quantisable_parameters(net) -> list[tuple[str, object]]:
    """Every weight tensor that would become int8 on the device.

    Selected by shape rather than by module type, and that is the point.
    `nn.MultiheadAttention` keeps its input projection as a raw parameter
    called `in_proj_weight` rather than as an `nn.Linear`, so a module-based
    sweep silently leaves it in float. On this configuration that is 6,144 of
    17,600 weights, 35% of the model, and skipping them would have understated
    the cost of quantisation by exactly the part most likely to suffer from it.

    Biases and one-dimensional tensors, which includes the layer-norm scales,
    are excluded. They are added into a 32-bit accumulator on the device too,
    so rounding them to 8 bits costs accuracy and saves nothing worth having.
    """
    return [(name, param) for name, param in net.named_parameters()
            if param.ndim >= 2]


def observed_modules(net) -> list[tuple[str, object]]:
    """Modules whose outputs are activation-quantisation points.

    `nn.MultiheadAttention` is included alongside `nn.Linear` because its
    output projection is applied functionally: a hook on `out_proj` never
    fires, so hooking the attention block is the only way to see the tensor
    that leaves it.
    """
    from torch import nn

    out = []
    for name, module in net.named_modules():
        if isinstance(module, nn.MultiheadAttention):
            out.append((name, module))
        elif isinstance(module, nn.Linear) and not name.endswith("out_proj"):
            out.append((name, module))
    return out


def _first_tensor(value):
    """Attention returns a tuple; a linear returns a tensor."""
    return value[0] if isinstance(value, tuple) else value


def _pin_cpu_threads(torch) -> None:
    """Hold PyTorch to one CPU thread before running a forward pass.

    Same platform fault as `evpil.forecast.models.fit_lstm` guards against, and
    it presents differently here: with XGBoost loaded in the same process, a
    CPU forward pass through the encoder segfaults rather than hanging. These
    two functions are the library's other entry points into a forward pass, so
    they carry the same guard. See `evpil.forecast._openmp`.
    """
    if torch.get_num_threads() != 1:
        torch.set_num_threads(1)


def calibrate_activations(trained, X_calibration: np.ndarray,
                          batch: int = 512) -> dict:
    """Observe activation ranges by running calibration windows through the net.

    `X_calibration` must come from training trips. Spec 5.2 is explicit that a
    calibration set built from test data is a subtle and common leak, and the
    same argument applies to validation: the numeric ranges the deployed model
    uses would then have been chosen with data it is about to be scored on.
    """
    import torch

    _pin_cpu_threads(torch)

    if len(X_calibration) == 0:
        raise ValueError("calibration set is empty")

    observers: dict[str, ActivationObserver] = {}
    handles = []

    def make_hook(key: str):
        def hook(module, inputs, output):
            tensor = _first_tensor(output)
            observers.setdefault(key, ActivationObserver()).observe(
                tensor.detach().cpu().numpy().reshape(-1)
            )
        return hook

    for name, module in observed_modules(trained.net):
        handles.append(module.register_forward_hook(make_hook(name)))

    try:
        trained.net.eval()
        with torch.no_grad():
            for start in range(0, len(X_calibration), batch):
                chunk = X_calibration[start:start + batch]
                xb = torch.from_numpy(trained.scaler.transform(chunk))
                trained.net(xb.to(trained.device))
    finally:
        for handle in handles:
            handle.remove()

    expected = {name for name, _ in observed_modules(trained.net)}
    missed = expected - set(observers)
    if missed:
        raise RuntimeError(
            f"no activations observed for {sorted(missed)}. A quantisation "
            f"sweep that silently skips a layer reports a cost that is too "
            f"low."
        )
    return {name: obs.to_range() for name, obs in observers.items()}


def predict_int8(trained, X: np.ndarray, activation_ranges: dict,
                 batch: int = 512) -> np.ndarray:
    """Run the network with int8 weights and int8 activations.

    Weights are rounded in place and restored afterwards. Activations are
    rounded at the output of every quantisation point using the calibrated
    ranges. Between those points the network computes in float, which is what
    an int8 kernel does as well: it accumulates in 32 bits and requantises on
    the way out.
    """
    import torch

    _pin_cpu_threads(torch)

    params = quantisable_parameters(trained.net)
    saved = [param.detach().clone() for _, param in params]
    handles = []

    def make_hook(rng: QuantRange):
        def hook(module, inputs, output):
            tensor = _first_tensor(output)
            fake = rng.fake_quantise(
                tensor.detach().cpu().numpy().astype(np.float64))
            replaced = torch.from_numpy(fake).to(tensor.dtype).to(tensor.device)
            if isinstance(output, tuple):
                return (replaced,) + tuple(output[1:])
            return replaced
        return hook

    try:
        with torch.no_grad():
            for _, param in params:
                values = param.detach().cpu().numpy().astype(np.float64)
                rng = QuantRange.symmetric_from(values)
                param.copy_(torch.from_numpy(rng.fake_quantise(values))
                            .to(param.dtype))

        for name, module in observed_modules(trained.net):
            if name in activation_ranges:
                handles.append(module.register_forward_hook(
                    make_hook(activation_ranges[name])))

        outputs = []
        trained.net.eval()
        with torch.no_grad():
            for start in range(0, len(X), batch):
                chunk = X[start:start + batch]
                xb = torch.from_numpy(trained.scaler.transform(chunk))
                outputs.append(
                    trained.net(xb.to(trained.device)).cpu().numpy()
                    .astype(np.float64))
    finally:
        for handle in handles:
            handle.remove()
        with torch.no_grad():
            for (_, param), original in zip(params, saved):
                param.copy_(original)

    return np.concatenate(outputs) * trained.y_sd + trained.y_mu


def deployed_bytes(net) -> int:
    """Bytes the deployed weights occupy: one per quantised weight, four per bias."""
    total = 0
    for _, param in net.named_parameters():
        total += param.numel() * (1 if param.ndim >= 2 else 4)
    return total
