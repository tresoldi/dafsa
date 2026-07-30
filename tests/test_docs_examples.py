"""Execute every ``python`` code block in the prose docs.

The README and the documentation site are full of runnable examples. This
extracts each fenced ``python`` block from those Markdown files and executes it,
so an example that references a renamed or non-existent API fails the test suite
instead of shipping. Docstring examples are covered separately, by doctest.

Conventions for doc authors:
* Each ``python`` block must run on its own in a fresh namespace -- import what
  it needs. Blocks do not share state.
* A block that is deliberately illustrative and not meant to run can opt out
  with a marker comment: ``# docs-test: skip``.

For a specific failure, the test id names the file and the 1-based block index.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOC_FILES = [
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "MIGRATION.md",
    _REPO_ROOT / "docs" / "USER_GUIDE.md",
]

_FENCE = re.compile(r"^```python\b[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
_SKIP = "# docs-test: skip"


def _blocks(path: Path) -> list[str]:
    """Return the ``python`` fenced code blocks in a Markdown file."""
    if not path.exists():
        return []

    return _FENCE.findall(path.read_text(encoding="utf-8"))


def _collect() -> list[tuple[str, int, str]]:
    """Collect ``(file, 1-based index, code)`` for every runnable block."""
    cases: list[tuple[str, int, str]] = []
    for path in _DOC_FILES:
        for index, block in enumerate(_blocks(path), start=1):
            if _SKIP not in block:
                cases.append((path.relative_to(_REPO_ROOT).as_posix(), index, block))

    return cases


_CASES = _collect()


def test_documentation_has_runnable_examples() -> None:
    assert _CASES, "no python blocks found; the extraction is broken"


@pytest.mark.parametrize(
    ("doc_file", "index", "code"),
    _CASES,
    ids=[f"{name}#block{index}" for name, index, _ in _CASES],
)
def test_doc_code_block_runs(doc_file: str, index: int, code: str) -> None:
    namespace: dict[str, object] = {"__name__": "__doc_example__"}
    compiled = compile(code, f"{doc_file}#block{index}", "exec")
    exec(compiled, namespace)
