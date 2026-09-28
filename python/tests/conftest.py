import json
import shutil
from pathlib import Path

import pytest

TESTDATA = Path(__file__).resolve().parents[2] / "testdata"


@pytest.fixture
def vectors() -> dict:
    return json.loads((TESTDATA / "vectors.json").read_text())


@pytest.fixture
def demo(tmp_path) -> tuple[Path, Path]:
    """A private copy of the demo fragment + proof, so cursors never touch testdata/."""
    fragment = tmp_path / "demo-fragment.bin"
    proof = tmp_path / "demo-fragment.proof.json"
    shutil.copy(TESTDATA / "demo-fragment.bin", fragment)
    shutil.copy(TESTDATA / "demo-fragment.proof.json", proof)
    return fragment, proof
