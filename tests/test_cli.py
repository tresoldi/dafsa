"""Tests for the command-line interface."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from dafsa.__main__ import build_parser, main

if TYPE_CHECKING:
    from pathlib import Path

needs_graphviz = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz is not installed")

WORDS = ["tap", "taps", "top", "tops", "dibs"]


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A file with one word per line."""
    source = tmp_path / "words.txt"
    source.write_text("\n".join(WORDS) + "\n", encoding="utf-8")

    return source


@pytest.fixture
def phrases(tmp_path: Path) -> Path:
    """Issue #17's input, one phrase per line."""
    source = tmp_path / "phrases.txt"
    source.write_text("a b c\na ab ac\na ab ab c\n", encoding="utf-8")

    return source


def run(*argv: str) -> int:
    """Run the interface with the given arguments."""
    return main(list(argv))


# -- structures ------------------------------------------------------------


def test_default_builds_a_dafsa(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(str(corpus)) == 0

    printed = capsys.readouterr().out
    assert "Dafsa over" in printed
    assert "sequences    5" in printed


@pytest.mark.parametrize(
    ("structure", "expected"),
    [("dafsa", "Dafsa"), ("trie", "Trie"), ("suffix", "SuffixAutomaton")],
)
def test_each_structure_can_be_selected(
    corpus: Path,
    capsys: pytest.CaptureFixture[str],
    structure: str,
    expected: str,
) -> None:
    assert run("-f", structure, str(corpus)) == 0
    assert expected in capsys.readouterr().out


def test_a_trie_is_larger_than_a_dafsa(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run("-f", "trie", str(corpus))
    trie = capsys.readouterr().out
    run("-f", "dafsa", str(corpus))
    dafsa = capsys.readouterr().out

    assert _states(trie) > _states(dafsa)


def _states(printed: str) -> int:
    """Pull the state count out of the text summary."""
    for line in printed.splitlines():
        if line.strip().startswith("states"):
            return int(line.split()[-1])

    raise AssertionError(printed)


def test_compact_shrinks_the_structure(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(str(corpus))
    plain = capsys.readouterr().out
    run("--compact", str(corpus))
    compacted = capsys.readouterr().out

    assert _states(compacted) < _states(plain)
    assert "compacted    yes" in compacted


def test_suffix_indexes_the_whole_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "text.txt"
    source.write_text("banana\n", encoding="utf-8")

    run("-f", "suffix", str(source))

    assert "SuffixAutomaton" in capsys.readouterr().out


# -- tokenization, which is issue #17 --------------------------------------


def test_characters_are_the_default(phrases: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Without a flag, a line is a sequence of characters — spaces included."""
    run(str(phrases))

    assert "over 4 tokens" in capsys.readouterr().out


def test_words_splits_on_whitespace(phrases: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Issue #17's expectation: a, ab, ac, b, c — and no space token."""
    run("--words", str(phrases))
    printed = capsys.readouterr().out

    assert "over 5 tokens" in printed
    assert "sequences    3" in printed


def test_sep_splits_on_a_given_separator(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "dashed.txt"
    source.write_text("a-b-c\na-b-d\n", encoding="utf-8")

    run("--sep", "-", str(source))

    assert "over 4 tokens" in capsys.readouterr().out


def test_sep_and_words_are_mutually_exclusive(corpus: Path) -> None:
    with pytest.raises(SystemExit):
        run("--sep", "-", "--words", str(corpus))


def test_an_empty_separator_is_rejected(corpus: Path) -> None:
    """``str.split("")`` raises; say so usefully instead."""
    with pytest.raises(SystemExit, match="use --words"):
        run("--sep", "", str(corpus))


def test_a_filename_is_not_eaten_by_sep(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The reason ``--sep`` takes a required value rather than an optional one."""
    assert run("--words", str(corpus)) == 0
    assert "Dafsa" in capsys.readouterr().out


# -- semirings -------------------------------------------------------------


def test_counting_reports_a_total(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "repeats.txt"
    source.write_text("tip\ntip\ntap\n", encoding="utf-8")

    run("-s", "counting", str(source))
    printed = capsys.readouterr().out

    assert "sequences    2" in printed
    assert "total weight 3" in printed


def test_push_requires_a_divisible_semiring(corpus: Path) -> None:
    with pytest.raises(NotImplementedError, match="not divisible"):
        run("--push", "-s", "counting", str(corpus))


def test_push_runs_under_a_divisible_semiring(
    corpus: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("--push", "-s", "probability", str(corpus)) == 0
    assert "Dafsa" in capsys.readouterr().out


# -- output ----------------------------------------------------------------


def test_json_output_is_valid(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run("-t", "json", str(corpus))

    assert json.loads(capsys.readouterr().out)["format"] == "dafsa"


def test_dot_output_declares_a_font(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run("-t", "dot", str(corpus))
    printed = capsys.readouterr().out

    assert 'charset="UTF-8"' in printed
    assert "DejaVu Sans" in printed


def test_the_font_can_be_chosen(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run("-t", "dot", "--font", "Noto Sans", str(corpus))

    assert 'fontname="Noto Sans"' in capsys.readouterr().out


def test_output_goes_to_a_file(corpus: Path, tmp_path: Path) -> None:
    destination = tmp_path / "out.json"
    run("-t", "json", "-o", str(destination), str(corpus))

    assert json.loads(destination.read_text(encoding="utf-8"))["format"] == "dafsa"


@pytest.mark.parametrize("fmt", ["gml", "graphml", "png"])
def test_formats_needing_a_file_say_so(corpus: Path, fmt: str) -> None:
    with pytest.raises(SystemExit, match="needs --output"):
        run("-t", fmt, str(corpus))


@pytest.mark.parametrize("fmt", ["gml", "graphml"])
def test_graph_formats_are_written(corpus: Path, tmp_path: Path, fmt: str) -> None:
    destination = tmp_path / f"out.{fmt}"
    run("-t", fmt, "-o", str(destination), str(corpus))

    assert destination.stat().st_size > 0


@needs_graphviz
@pytest.mark.parametrize("fmt", ["png", "svg", "pdf"])
def test_images_are_rendered(corpus: Path, tmp_path: Path, fmt: str) -> None:
    destination = tmp_path / f"out.{fmt}"
    run("-t", fmt, "-o", str(destination), "--dpi", "72", str(corpus))

    assert destination.stat().st_size > 0


@needs_graphviz
def test_label_nodes_reaches_the_drawing(corpus: Path, tmp_path: Path) -> None:
    destination = tmp_path / "out.svg"
    run("-t", "svg", "-o", str(destination), "--label-nodes", str(corpus))

    assert ">1<" in destination.read_text(encoding="utf-8")


def test_scale_edges_reaches_the_drawing(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run("-t", "dot", "--scale-edges", str(corpus))

    assert "penwidth=" in capsys.readouterr().out


def test_label_sep_reaches_the_drawing(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run("-t", "dot", "--compact", "--label-sep", "-", str(corpus))

    assert "-" in capsys.readouterr().out


# -- plumbing --------------------------------------------------------------


def test_reads_standard_input(
    corpus: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with corpus.open(encoding="utf-8") as handle:
        monkeypatch.setattr("sys.stdin", handle)

        assert run("-") == 0

    assert "Dafsa" in capsys.readouterr().out


def test_blank_lines_are_ignored(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "gappy.txt"
    source.write_text("tap\n\n\ntop\n", encoding="utf-8")

    run(str(source))

    assert "sequences    2" in capsys.readouterr().out


def test_an_empty_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "empty.txt"
    source.write_text("", encoding="utf-8")

    assert run(str(source)) == 0
    assert "sequences    0" in capsys.readouterr().out


def test_an_empty_file_as_a_suffix_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "empty.txt"
    source.write_text("", encoding="utf-8")

    assert run("-f", "suffix", str(source)) == 0
    assert "SuffixAutomaton" in capsys.readouterr().out


def test_a_missing_file_reports_itself(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        run(str(tmp_path / "absent.txt"))


def test_the_parser_can_be_built_without_running() -> None:
    parser = build_parser()

    assert parser.prog == "dafsa"
    assert parser.parse_args(["file"]).structure == "dafsa"


def test_version_is_reported() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "dafsa", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.startswith("dafsa ")


def test_help_mentions_the_tokenization_flags() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "dafsa", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--words" in result.stdout
    assert "--sep" in result.stdout
