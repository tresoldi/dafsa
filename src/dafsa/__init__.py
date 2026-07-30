"""Finite-state structures for sequence data.

This is the 2.0 development line, a clean break from 1.0. The public API is
described in ``DESIGN.md`` at the root of the repository; the structures
themselves land over the milestones listed there, and this package currently
exposes only its metadata.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dafsa")
except PackageNotFoundError:  # pragma: no cover - source tree without install
    __version__ = "0.0.0.dev0"

__author__ = "Tiago Tresoldi"
__email__ = "tiago.tresoldi@lingfil.uu.se"

__all__ = ["__version__"]
