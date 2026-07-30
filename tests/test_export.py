"""Tests for the export layer.

The regression tests for #15 and #16 are at the end. Where an export depends on
Graphviz, the test runs it and checks the result rather than checking only that
we produced plausible-looking text — a DOT file that Graphviz rejects is not an
export.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

import networkx as nx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dafsa import Dafsa, Trie, tokenize
from dafsa._builder import Builder
from dafsa.alphabet import Alphabet
from dafsa.automaton import ROOT
from dafsa.exceptions import ExportError
from dafsa.export import (
    DEFAULT_CHARSET,
    DEFAULT_FONT,
    to_dict,
    to_dot,
    to_json,
    to_networkx,
    write_figure,
    write_gml,
    write_graphml,
)
from dafsa.semirings import COUNTING

if TYPE_CHECKING:
    from pathlib import Path

WORDS = ["tap", "taps", "top", "tops", "dibs"]

WORD_LISTS = st.lists(st.text(alphabet="abc", max_size=4), max_size=8)

needs_graphviz = pytest.mark.skipif(
    shutil.which("dot") is None, reason="Graphviz is not installed"
)


# -- dictionaries and JSON -------------------------------------------------


def test_to_dict_describes_the_structure() -> None:
    described = to_dict(Dafsa.from_sequences(["ab", "ac"]))

    assert described["format"] == "dafsa"
    assert described["type"] == "Dafsa"
    assert described["semiring"] == "BooleanSemiring"
    assert described["weighted"] is False
    assert described["compact"] is False
    assert described["alphabet"] == ["a", "b", "c"]
    # Minimized: "b" and "c" lead to the same accepting state.
    assert len(described["states"]) == 3
    assert len(described["transitions"]) == 3


def test_to_dict_omits_weights_when_there_are_none() -> None:
    """A uniform ``one`` everywhere would be noise, not information."""
    described = to_dict(Dafsa.from_sequences(["ab"]))

    assert all("weight" not in edge for edge in described["transitions"])
    assert all("final_weight" not in state for state in described["states"])


def test_to_dict_includes_weights_when_there_are_some() -> None:
    described = to_dict(Dafsa.from_weighted([("ab", 3), ("cd", 5)], semiring=COUNTING))

    assert described["weighted"] is True
    assert described["semiring"] == "CountingSemiring"
    assert {s["final_weight"] for s in described["states"] if s["final"]} == {3, 5}


def test_to_dict_records_compound_labels() -> None:
    described = to_dict(Dafsa.from_sequences(["tapas", "topos"]).compact())

    assert described["compact"] is True
    assert described["type"] == "CompactDafsa"
    labels = sorted("".join(edge["label"]) for edge in described["transitions"])
    assert labels == ["apa", "opo", "s", "t"]


@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_to_dict_edge_count_matches_the_automaton(words: list[str]) -> None:
    automaton = Dafsa.from_sequences(words)
    described = to_dict(automaton)

    assert len(described["states"]) == automaton.num_states
    assert len(described["transitions"]) == automaton.num_transitions


def test_to_json_is_valid_json() -> None:
    parsed = json.loads(to_json(Dafsa.from_sequences(WORDS)))

    assert parsed["format"] == "dafsa"
    assert parsed["alphabet"] == ["a", "b", "d", "i", "o", "p", "s", "t"]


def test_to_json_writes_to_a_path(tmp_path: Path) -> None:
    destination = tmp_path / "automaton.json"
    text = to_json(Dafsa.from_sequences(["ab"]), destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == json.loads(text)


def test_to_json_survives_tokens_it_cannot_represent() -> None:
    """Lossy on purpose: there is no reader, so fidelity buys nothing here."""

    class Opaque:
        def __repr__(self) -> str:
            return "<opaque>"

    sequences: list[tuple[Any, ...]] = [(Opaque(),)]
    parsed = json.loads(to_json(Dafsa.from_sequences(sequences)))

    assert parsed["alphabet"] == ["<opaque>"]


def test_to_json_handles_non_string_tokens() -> None:
    parsed = json.loads(to_json(Dafsa.from_sequences([tokenize("the cat")])))

    assert parsed["alphabet"] == ["cat", "the"]


def test_to_json_of_an_empty_automaton() -> None:
    parsed = json.loads(to_json(Dafsa.from_sequences([])))

    assert parsed["states"] == [{"id": 0, "final": False}]
    assert parsed["transitions"] == []


# -- DOT -------------------------------------------------------------------


def test_to_dot_declares_a_charset_and_a_font() -> None:
    source = to_dot(Dafsa.from_sequences(["ab"]))

    assert f'charset="{DEFAULT_CHARSET}"' in source
    assert source.count(f'fontname="{DEFAULT_FONT}"') == 3  # graph, node, edge


def test_to_dot_accepts_a_different_font() -> None:
    source = to_dot(Dafsa.from_sequences(["ab"]), fontname="Noto Sans")

    assert 'fontname="Noto Sans"' in source
    assert DEFAULT_FONT not in source


def test_to_dot_marks_the_root_and_the_final_states() -> None:
    source = to_dot(Dafsa.from_sequences(["ab"]))

    assert '"0" [label="", shape="doubleoctagon"]' in source
    assert 'shape="doublecircle"' in source
    assert 'shape="circle"' in source


def test_to_dot_can_label_nodes() -> None:
    source = to_dot(Dafsa.from_sequences(["ab"]), label_nodes=True)

    assert '"1" [label="1"' in source


def test_to_dot_escapes_labels() -> None:
    """A quote or backslash in a token would otherwise end the attribute early."""
    sequences: list[tuple[str, ...]] = [('say "hi"', "back\\slash", "two\nlines")]
    source = to_dot(Dafsa.from_sequences(sequences))

    assert r"\"hi\"" in source
    assert "back\\\\slash" in source
    assert "two\\nlines" in source
    assert "\r" not in source


def test_to_dot_joins_single_characters_without_a_separator() -> None:
    source = to_dot(Dafsa.from_sequences(["tapas", "topos"]).compact())

    assert 'label="apa"' in source
    assert 'label="opo"' in source


def test_to_dot_separates_multi_character_tokens() -> None:
    """Running word tokens together would be unreadable."""
    sequences = [tokenize("the big cat")]
    source = to_dot(Dafsa.from_sequences(sequences).compact())

    assert 'label="the big cat"' in source


def test_to_dot_accepts_an_explicit_separator() -> None:
    source = to_dot(Dafsa.from_sequences(["tapas", "topos"]).compact(), label_sep="-")

    assert 'label="a-p-a"' in source


def test_to_dot_of_an_empty_automaton() -> None:
    """1.0 raised ``ValueError`` here, from ``max()`` on an empty sequence."""
    source = to_dot(Dafsa.from_sequences([]))

    assert '"0" [' in source
    assert "->" not in source


def test_to_dot_of_an_unweighted_automaton_does_not_divide_by_zero() -> None:
    """The direct 1.0 regression: ``node.weight / max_weight`` with all weights zero."""
    source = to_dot(Dafsa.from_sequences(WORDS), scale_edges=True)

    assert "penwidth=" in source


def test_edge_scaling_is_off_by_default() -> None:
    assert "penwidth=" not in to_dot(Dafsa.from_sequences(WORDS))


def test_edge_scaling_is_guarded_on_an_empty_language() -> None:
    """Every subtree is empty, so every ratio would be zero over zero."""
    source = to_dot(Dafsa.from_sequences([]), scale_edges=True)

    assert "digraph" in source


def test_edge_scaling_makes_busier_edges_thicker() -> None:
    automaton = Dafsa.from_sequences(["ax", "ay", "az", "b"])
    source = to_dot(automaton, scale_edges=True, label_nodes=True)

    widths = {
        line.split('label="')[1].split('"')[0]: float(
            line.split("penwidth=")[1].rstrip("];\n")
        )
        for line in source.splitlines()
        if "->" in line and "penwidth=" in line
    }

    assert widths["a"] > widths["b"]


@settings(deadline=None, max_examples=50)
@given(words=WORD_LISTS)
def test_to_dot_emits_one_edge_per_transition(words: list[str]) -> None:
    automaton = Dafsa.from_sequences(words)
    source = to_dot(automaton)

    assert source.count("->") == automaton.num_transitions


# -- Graphviz actually parsing it -----------------------------------------


@needs_graphviz
@pytest.mark.parametrize(
    "automaton",
    [
        Dafsa.from_sequences(WORDS),
        Dafsa.from_sequences(WORDS).compact(),
        Dafsa.from_sequences([]),
        Dafsa.from_sequences([tokenize("the big cat"), tokenize("the big dog")]),
        Dafsa.from_sequences(["aimâmes", "aimèrent"]),
    ],
    ids=["plain", "compact", "empty", "words", "accented"],
)
def test_graphviz_accepts_the_generated_source(automaton: Any) -> None:
    """Text that Graphviz rejects is not an export."""
    result = subprocess.run(
        ["dot", "-Tsvg"],
        input=to_dot(automaton),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "<svg" in result.stdout


@needs_graphviz
def test_graphviz_accepts_escaped_labels() -> None:
    sequences: list[tuple[str, ...]] = [('a "quoted" token', "back\\slash")]
    result = subprocess.run(
        ["dot", "-Tsvg"],
        input=to_dot(Dafsa.from_sequences(sequences)),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@needs_graphviz
@pytest.mark.parametrize("suffix", ["svg", "png", "pdf", "dot"])
def test_write_figure_renders(tmp_path: Path, suffix: str) -> None:
    destination = tmp_path / f"automaton.{suffix}"
    write_figure(Dafsa.from_sequences(WORDS), destination)

    assert destination.exists()
    assert destination.stat().st_size > 0


@needs_graphviz
def test_write_figure_passes_options_through(tmp_path: Path) -> None:
    destination = tmp_path / "automaton.svg"
    write_figure(Dafsa.from_sequences(["ab"]), destination, label_nodes=True)

    assert ">1<" in destination.read_text(encoding="utf-8")


def test_write_figure_needs_an_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="infer an output format"):
        write_figure(Dafsa.from_sequences(["ab"]), tmp_path / "nameless")


def test_write_figure_reports_a_missing_graphviz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def absent(*_args: Any, **_kwargs: Any) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", absent)

    with pytest.raises(ExportError, match="Graphviz is required"):
        write_figure(Dafsa.from_sequences(["ab"]), tmp_path / "out.png")


def test_write_figure_reports_a_graphviz_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(*_args: Any, **_kwargs: Any) -> None:
        raise subprocess.CalledProcessError(1, "dot", stderr=b"syntax error")

    monkeypatch.setattr(subprocess, "run", failing)

    with pytest.raises(ExportError, match="syntax error"):
        write_figure(Dafsa.from_sequences(["ab"]), tmp_path / "out.png")


# -- networkx --------------------------------------------------------------


def test_to_networkx_is_a_directed_multigraph() -> None:
    graph = to_networkx(Dafsa.from_sequences(WORDS))

    assert isinstance(graph, nx.MultiDiGraph)
    assert graph.is_directed()
    assert graph.is_multigraph()


@settings(deadline=None, max_examples=100)
@given(words=WORD_LISTS)
def test_to_networkx_has_one_edge_per_transition(words: list[str]) -> None:
    """1.0 re-added every edge once per node, which is O(n squared) of them."""
    automaton = Dafsa.from_sequences(words)
    graph = to_networkx(automaton)

    assert graph.number_of_nodes() == automaton.num_states
    assert graph.number_of_edges() == automaton.num_transitions


def test_to_networkx_directions_point_the_right_way() -> None:
    automaton = Dafsa.from_sequences(["ab"])
    graph = to_networkx(automaton)

    assert graph.has_edge(0, 1)
    assert not graph.has_edge(1, 0)


def test_to_networkx_marks_root_and_final_states() -> None:
    graph = to_networkx(Dafsa.from_sequences(["ab"]))

    assert graph.nodes[ROOT]["root"] is True
    assert graph.nodes[ROOT]["final"] is False
    assert any(data["final"] for _, data in graph.nodes(data=True))


def test_to_networkx_carries_weights() -> None:
    graph = to_networkx(Dafsa.from_weighted([("ab", 4)], semiring=COUNTING))
    finals = [
        data["final_weight"] for _, data in graph.nodes(data=True) if data["final"]
    ]

    assert finals == [4]


def test_to_networkx_carries_compound_labels() -> None:
    graph = to_networkx(Dafsa.from_sequences(["tapas", "topos"]).compact())
    labels = sorted(data["label"] for _, _, data in graph.edges(data=True))

    assert labels == ["apa", "opo", "s", "t"]


# -- GML and GraphML -------------------------------------------------------


def test_write_gml_round_trips_through_networkx(tmp_path: Path) -> None:
    automaton = Dafsa.from_sequences(WORDS)
    destination = tmp_path / "automaton.gml"
    write_gml(automaton, destination)

    restored = nx.read_gml(destination)

    assert restored.number_of_nodes() == automaton.num_states
    assert restored.number_of_edges() == automaton.num_transitions
    assert restored.is_directed()


def test_write_graphml_round_trips_through_networkx(tmp_path: Path) -> None:
    automaton = Dafsa.from_sequences(WORDS)
    destination = tmp_path / "automaton.graphml"
    write_graphml(automaton, destination)

    restored = nx.read_graphml(destination)

    assert restored.number_of_nodes() == automaton.num_states
    assert restored.number_of_edges() == automaton.num_transitions


def test_gml_survives_tuple_valued_attributes(tmp_path: Path) -> None:
    """GML takes scalars only, and a compound label is a tuple."""
    automaton = Dafsa.from_sequences(["tapas", "topos"]).compact()
    destination = tmp_path / "automaton.gml"
    write_gml(automaton, destination)

    assert "apa" in destination.read_text(encoding="utf-8")


def test_graphml_survives_weighted_automata(tmp_path: Path) -> None:
    automaton = Dafsa.from_weighted([("ab", 3)], semiring=COUNTING)
    destination = tmp_path / "automaton.graphml"
    write_graphml(automaton, destination)

    assert destination.stat().st_size > 0


# -- regressions -----------------------------------------------------------


def test_issue_16_the_graph_is_directed() -> None:
    """``to_graph()`` returned ``nx.Graph`` while documenting a directed one."""
    graph = to_networkx(Dafsa.from_sequences(WORDS))

    assert graph.is_directed()


def test_issue_16_parallel_edges_keep_their_own_labels() -> None:
    """The half of #16 the report did not mention.

    ``am`` and ``an`` share a source and a target, so 1.0 wrote both labels into
    ``graph[l][r]["label"]`` and the second silently replaced the first. A
    multigraph gives each transition its own slot.
    """
    automaton = Dafsa.from_sequences(["am", "an"])
    graph = to_networkx(automaton)

    branch = automaton.step(ROOT, automaton.alphabet.id("a"))
    assert branch is not None
    parallel = graph.get_edge_data(branch, automaton.transition_target(1))

    assert parallel is not None
    assert sorted(data["label"] for data in parallel.values()) == ["m", "n"]


@needs_graphviz
def test_issue_15_the_named_font_is_the_one_embedded(tmp_path: Path) -> None:
    """The reporter's input: French verb forms, rendered to PDF as boxes in 1.0.

    Graphviz embeds the font it resolved, so the PDF names it. Asking for a font
    with the coverage is what the fix consists of; 1.0's template asked for none
    and took whatever the system defaulted to.
    """
    automaton = Dafsa.from_sequences(
        ["aime", "aimes", "aimons", "aimez", "aiment", "aimâmes", "aimâtes", "aimèrent"]
    )
    destination = tmp_path / "verbs.pdf"
    write_figure(automaton, destination)

    assert b"DejaVuSans" in destination.read_bytes()


@needs_graphviz
def test_issue_15_accented_tokens_survive_to_svg(tmp_path: Path) -> None:
    automaton = Dafsa.from_sequences(["aimâmes", "aimèrent"])
    destination = tmp_path / "verbs.svg"
    write_figure(automaton, destination)

    rendered = destination.read_text(encoding="utf-8")

    assert "â" in rendered
    assert "è" in rendered
    assert DEFAULT_FONT in rendered


@needs_graphviz
def test_non_latin_tokens_render(tmp_path: Path) -> None:
    """The general case the font fix is for."""
    automaton = Dafsa.from_sequences(["ʃiːp", "ʃɪp"])
    destination = tmp_path / "phonemes.svg"
    write_figure(automaton, destination)

    assert "ʃ" in destination.read_text(encoding="utf-8")


def test_edge_scaling_survives_a_dead_state() -> None:
    """Every subtree empty while transitions exist — the 1.0 division by zero.

    Construction never produces a state that cannot reach acceptance, so this is
    built by hand; the guard has to hold regardless of how the automaton arrived.
    """
    alphabet = Alphabet("ab")
    builder = Builder(alphabet)
    dead = builder.new_state()
    builder.add_transition(ROOT, alphabet.id("a"), dead)

    source = to_dot(builder.freeze(), scale_edges=True)

    assert "penwidth=1.00" in source


@settings(deadline=None, max_examples=50)
@given(words=WORD_LISTS)
def test_every_export_runs_on_anything(words: list[str]) -> None:
    """None of these was a wrong answer in 1.0 — they were crashes."""
    for automaton in (
        Dafsa.from_sequences(words),
        Trie.from_sequences(words),
        Dafsa.from_sequences(words).compact(),
    ):
        to_dot(automaton, scale_edges=True)
        to_json(automaton)
        to_networkx(automaton)
