"""Packaging and infrastructure checks.

These guard the milestone 0 scaffolding: the package imports, its version has a
single source, it advertises inline types, and the console script is wired up.
The tests for the structures themselves arrive with the structures.
"""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

import dafsa
from dafsa.__main__ import main


def test_version_is_importable() -> None:
    assert isinstance(dafsa.__version__, str)
    assert dafsa.__version__


def test_version_has_a_single_source() -> None:
    """``dafsa.__version__`` is the source; the metadata must be read from it."""
    assert dafsa.__version__ == version("dafsa")


def test_package_ships_a_typing_marker() -> None:
    marker = Path(dafsa.__file__).parent / "py.typed"
    assert marker.is_file()


def test_requires_supported_python() -> None:
    assert sys.version_info >= (3, 10)


@pytest.mark.parametrize("flag", ["--version", "--help"])
def test_module_runs_as_a_script(flag: str) -> None:
    """``python -m dafsa`` must work, which the in-process tests cannot cover."""
    result = subprocess.run(
        [sys.executable, "-m", "dafsa", flag],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip()


def test_main_with_no_arguments_asks_for_a_source(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The interface reads sequences from somewhere, so a source is required."""
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code != 0
    assert "source" in capsys.readouterr().err


def test_main_reports_the_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])

    assert excinfo.value.code == 0
    assert dafsa.__version__ in capsys.readouterr().out
