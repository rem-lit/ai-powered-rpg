from pathlib import Path

import pytest

from mj.univers import charger_univers

RACINE = Path(__file__).resolve().parents[1]


@pytest.fixture
def racine() -> Path:
    return RACINE


@pytest.fixture
def logres():
    return charger_univers(RACINE / "universes" / "logres.yaml")
