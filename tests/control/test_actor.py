import numpy as np
import pytest

from evpil.control.actor import Actor, write_c_header


def tiny_actor(n_in=3, hidden=4, n_out=2, seed=0) -> Actor:
    rng = np.random.default_rng(seed)
    sizes = [n_in, hidden, n_out]
    return Actor(
        weights=[rng.normal(size=(sizes[i + 1], sizes[i])).astype(np.float32)
                 for i in range(2)],
        biases=[rng.normal(size=sizes[i + 1]).astype(np.float32)
                for i in range(2)],
        obs_scale=np.ones(n_in, dtype=np.float32), obs_clip=10.0,
        action_low=-np.ones(n_out, dtype=np.float32),
        action_high=np.ones(n_out, dtype=np.float32),
    )


def test_the_forward_pass_is_relu_hidden_and_tanh_output():
    a = tiny_actor()
    x = np.array([0.3, -1.2, 0.7])
    h = np.maximum(a.weights[0] @ x + a.biases[0], 0.0)
    want = np.tanh(a.weights[1] @ h + a.biases[1])
    assert a.forward(x) == pytest.approx(want, rel=1e-12)


def test_the_action_is_always_inside_the_actuator_range():
    """tanh, not a clamp. An action outside [-1, 1] would decode to a
    regeneration blend above 1 or a negative one, and nothing downstream of
    the decoder checks for that."""
    a = tiny_actor()
    for scale in (0.0, 1.0, 1e3, 1e6):
        out = a.forward(np.full(3, scale))
        assert np.all(np.abs(out) <= 1.0)


def test_saving_and_loading_returns_the_same_network(tmp_path):
    a = tiny_actor()
    path = tmp_path / "actor.npz"
    a.save(path)
    b = Actor.load(path)
    x = np.array([0.1, 0.2, 0.3])
    assert b.forward(x) == pytest.approx(a.forward(x), rel=1e-12)
    assert b.layer_sizes == a.layer_sizes
    assert b.obs_clip == a.obs_clip


def test_the_cost_model_counts_what_it_says_it_counts():
    a = tiny_actor(n_in=8, hidden=64, n_out=3)
    c = a.cost()
    # Two layers: 64x8 and 3x64 multiply-accumulates.
    assert c["macs"] == 64 * 8 + 3 * 64
    assert c["n_params"] == (64 * 8 + 64) + (3 * 64 + 3)
    assert c["footprint_kb"] == pytest.approx(c["n_params"] * 4 / 1024)
    assert a.cost(int8=True)["footprint_kb"] == pytest.approx(
        c["footprint_kb"] / 4)


def two_hidden(width: int) -> Actor:
    """The shape SB3 actually builds: two hidden layers of `width`."""
    rng = np.random.default_rng(1)
    sizes = [8, width, width, 3]
    return Actor(
        weights=[rng.normal(size=(sizes[i + 1], sizes[i])).astype(np.float32)
                 for i in range(3)],
        biases=[rng.normal(size=sizes[i + 1]).astype(np.float32)
                for i in range(3)],
        obs_scale=np.ones(8, dtype=np.float32), obs_clip=10.0,
        action_low=-np.ones(3, dtype=np.float32),
        action_high=np.ones(3, dtype=np.float32),
    )


def test_the_library_default_width_would_not_fit_beside_the_forecaster():
    """The reason net_arch is 64 and not the library's 256. The quantised
    forecaster already holds 20.2 KB of the 300 KB G5 budget, and a 256-wide
    actor asks for 269 of what is left."""
    assert two_hidden(256).cost()["footprint_kb"] > 250.0
    assert two_hidden(64).cost()["footprint_kb"] < 25.0


def test_the_generated_header_declares_the_geometry_it_contains(tmp_path):
    a = tiny_actor(n_in=8, hidden=16, n_out=3)
    path = tmp_path / "w.h"
    write_c_header(a, path)
    text = path.read_text()

    assert "#define SAC_ACTOR_N_LAYERS 2" in text
    assert "#define SAC_ACTOR_N_IN  8" in text
    assert "#define SAC_ACTOR_N_OUT 3" in text
    assert "#define SAC_ACTOR_MAX_WIDTH 16" in text
    assert "Do not edit" in text

    # Round weights are the ones that break: "{10.0:.8g}f" is "10f", which is
    # not a C float literal. Every one of these compiled before the fix and
    # none of them would have.
    assert "10f" not in text and " 2f" not in text

    # Every weight reaches the header, in the count the array declares.
    for i, w in enumerate(a.weights):
        assert f"static const float sac_actor_w{i}[{w.size}]" in text
    for i, b in enumerate(a.biases):
        assert f"static const float sac_actor_b{i}[{b.size}]" in text


def test_the_header_is_row_major_in_the_order_the_c_code_reads(tmp_path):
    """firmware/main/actor.c indexes `w + j * n_in`. If the export flattened
    column-major the network would still run and would compute something
    else."""
    a = tiny_actor(n_in=3, hidden=2, n_out=2)
    path = tmp_path / "w.h"
    write_c_header(a, path)
    text = path.read_text()
    block = text.split("sac_actor_w0[6] = {")[1].split("};")[0]
    got = [float(v.strip().rstrip("f")) for v in block.replace("\n", "")
           .split(",") if v.strip()]
    assert got == pytest.approx(a.weights[0].reshape(-1), rel=1e-6)
