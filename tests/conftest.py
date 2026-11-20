import warnings

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

warnings.filterwarnings("ignore")


@pytest.fixture(autouse=True)
def _close_figures(monkeypatch, tmp_path):
    # isolate from any pyproject.toml above the test run
    monkeypatch.chdir(tmp_path)
    yield
    plt.close("all")


@pytest.fixture
def regions():
    return pd.DataFrame(
        {
            "region_name": ["West", "East", "South", "North", "Central"],
            "avg_income_usd": [52.0, 61.0, 47.0, 58.0, 50.0],
        }
    )


@pytest.fixture
def cloud():
    rng = np.random.default_rng(0)
    return pd.DataFrame({"x": rng.normal(size=3000), "y": rng.normal(size=3000)})


def ids(report):
    return set(report.ids)
