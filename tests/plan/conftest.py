import json
from pathlib import Path

import numpy as np
import pytest

from evpil.plant.auxiliary import AuxParams
from scripts.identify_params import build_params

PARAMS_JSON = Path("data/i3_params.json")


@pytest.fixture(scope="session")
def params():
    """The identified i3, or a skip when identification has not been run.

    The controller tests are about the controller, but they need a vehicle
    that is not made up: gains that look stable against invented parameters
    say nothing about the ones that will be flashed.
    """
    if not PARAMS_JSON.exists():
        pytest.skip("data/i3_params.json not present; run scripts/identify_params.py")
    d = json.loads(PARAMS_JSON.read_text())
    i = d["identified"]
    return build_params(i["c_rr"], i["cd"], i["r0_ohm"], AuxParams(**d["aux"]),
                        i["rot_mass_factor"], np.array(d["motor_efficiency_grid"]))
