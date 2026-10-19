"""Exercise the actual Uno sketch with simulated serial input and servos."""

from pathlib import Path
import shutil
import subprocess

import pytest


def test_uno_sketch_handles_pc_test_and_coin_protocols(tmp_path):
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("native C++ compiler is not installed")
    support = Path(__file__).parent / "firmware"
    binary = tmp_path / "uno-protocol-test"
    subprocess.run(
        [compiler, "-std=c++17", "-I", str(support),
         str(support / "uno_protocol.cpp"), "-o", str(binary)],
        check=True, capture_output=True, text=True,
    )
    subprocess.run([str(binary)], check=True, timeout=10)
