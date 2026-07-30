"""Rendering a frozen automaton into other formats.

Nothing in the core knows about Graphviz, networkx, or JSON; everything that does
is here. Exports are one-way by design — the sequences are the source of truth
and rebuilding is fast — so nothing in this module has a reader counterpart.

Three of the exports here answer reported bugs.

**Fonts (#15).** 1.0 rendered through a template that declared neither a charset
nor a font, so Graphviz fell back to a default face with no coverage for most of
what a linguist would want to draw and emitted its missing-glyph box. The emitter
below sets ``charset`` and ``fontname`` on the graph and on both node and edge
defaults.

**Direction and parallel edges (#16).** 1.0's ``to_graph()`` built an
``nx.Graph`` while documenting a directed one, re-added every edge once per node,
and wrote each edge's label into a single slot — so when two transitions joined
the same pair of states, one label overwrote the other. This builds an
``nx.MultiDiGraph`` in one pass, one edge per transition, each keeping its own
label and weight.

**Division by zero.** 1.0 scaled node sizes by ``node.weight / max_weight``,
which raised ``ZeroDivisionError`` whenever an automaton was built with
``weight=False``, and ``ValueError`` on an empty one. Scaling here is opt-in and
guarded at both ends.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dafsa._types import ROOT
from dafsa.exceptions import ExportError

if TYPE_CHECKING:
    import networkx as nx

    from dafsa._types import Token
    from dafsa.automaton import Automaton


def _networkx() -> Any:
    """Return the ``networkx`` module, or explain why it is missing.

    Imported here rather than at the top of the module because it is an optional
    dependency. Nothing in the library needs it — construction, minimization,
    counting, ranking, composition and the DOT output are all plain Python — so
    making it required would charge every user for three functions most of them
    will not call.

    Returns:
        The ``networkx`` module.

    Raises:
        ExportError: If it is not installed.
    """
    try:
        import networkx as nx  # Deferred: networkx is optional, so importing it eagerly would make the
    # whole module unimportable without the `graph` extra.
    except ImportError as error:
        message = (
            "this export needs networkx, which is an optional dependency; "
            "install it with `pip install dafsa[graph]`"
        )
        raise ExportError(message) from error

    return nx


#: Emitted into every DOT source so Graphviz reads the labels as UTF-8.
DEFAULT_CHARSET = "UTF-8"

#: A font with coverage well beyond Latin-1, which is the point of naming one at
#: all. Graphviz's own default has none, and silently draws boxes instead.
DEFAULT_FONT = "DejaVu Sans"

_MIN_PEN_WIDTH = 1.0


# -- dictionaries and JSON -------------------------------------------------


def to_dict(automaton: Automaton) -> dict[str, Any]:
    """Return a plain-data description of ``automaton``.

    Tokens and weights are included as they are, not stringified, so the result
    is faithful for any caller willing to handle Python objects. ``to_json``
    is the lossy step.

    Args:
        automaton: The automaton to describe.

    Returns:
        Keys: ``format``, ``version``, ``type``, ``semiring``, ``weighted``,
        ``compact``, ``alphabet``, ``states`` and ``transitions``. Per-item
        weights appear only when the automaton is weighted, since a uniform
        ``one`` everywhere carries no information.

    Examples:
        >>> from dafsa import Dafsa
        >>> described = to_dict(Dafsa.from_sequences(["ab"]))
        >>> described["type"], described["alphabet"], len(described["transitions"])
        ('Dafsa', ['a', 'b'], 2)
    """
    weighted = automaton.is_weighted

    states: list[dict[str, Any]] = []
    for state in automaton.states():
        entry: dict[str, Any] = {"id": state, "final": automaton.is_final(state)}
        if weighted and automaton.is_final(state):
            entry["final_weight"] = automaton.final_weight(state)
        states.append(entry)

    transitions: list[dict[str, Any]] = []
    for state in automaton.states():
        for index in automaton.transition_indices(state):
            edge: dict[str, Any] = {
                "source": state,
                "target": automaton.transition_target(index),
                "label": list(automaton.transition_tokens(index)),
            }
            if weighted:
                edge["weight"] = automaton.transition_weight(index)
            transitions.append(edge)

    return {
        "format": "dafsa",
        "version": 1,
        "type": type(automaton).__name__,
        "semiring": type(automaton.semiring).__name__,
        "weighted": weighted,
        "compact": automaton.is_compact,
        **({"initial_weight": automaton.initial_weight} if weighted else {}),
        "alphabet": list(automaton.alphabet.tokens),
        "states": states,
        "transitions": transitions,
    }


def to_json(
    automaton: Automaton,
    path: str | Path | None = None,
    *,
    indent: int | None = 2,
) -> str:
    """Serialise ``automaton`` as JSON.

    Tokens that JSON cannot represent are written as their ``repr``. That is
    lossy, and acceptable, because there is no reader: the export exists to be
    inspected and to feed other tools, not to round-trip.

    Args:
        automaton: The automaton to serialise.
        path: Where to write. ``None`` returns the text without writing.
        indent: Indentation passed to ``json.dumps``. ``None`` gives compact output.

    Returns:
        The JSON text.
    """
    text = json.dumps(to_dict(automaton), indent=indent, default=repr)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")

    return text


# -- Graphviz --------------------------------------------------------------


def _escape(text: str) -> str:
    """Escape a string for use inside a quoted DOT attribute."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def _join(tokens: tuple[Token, ...], separator: str | None) -> str:
    """Render a transition's tokens as a display label.

    Args:
        tokens: The tokens the transition consumes.
        separator: What to put between them. ``None`` chooses: nothing between
            single-character strings, which reads as a word, and a space otherwise,
            which keeps multi-character tokens apart.

    Returns:
        The joined label.
    """
    if separator is None:
        separator = (
            "" if all(isinstance(token, str) and len(token) == 1 for token in tokens) else " "
        )

    return separator.join(str(token) for token in tokens)


def _pen_widths(automaton: Automaton, scale: float) -> dict[int, float]:
    """Return a pen width per transition index, scaled by subtree size.

    Thickness tracks how many sequences run through a transition, which is what
    makes a drawing readable at a glance. Both degenerate cases are handled: an
    automaton accepting nothing, and one where every subtree is the same size.

    Args:
        automaton: The automaton being drawn.
        scale: How much thicker the busiest edge should be than the thinnest.

    Returns:
        Transition index to pen width.
    """
    counts = {
        index: automaton.suffix_count(automaton.transition_target(index))
        for state in automaton.states()
        for index in automaton.transition_indices(state)
    }
    if not counts:
        return {}

    largest = max(counts.values())
    if largest <= 0:
        return dict.fromkeys(counts, _MIN_PEN_WIDTH)

    return {
        index: _MIN_PEN_WIDTH + scale * (count / largest) ** 0.5 for index, count in counts.items()
    }


def to_dot(  # Rendering options, each independent of the others.
    automaton: Automaton,
    *,
    label_nodes: bool = False,
    fontname: str = DEFAULT_FONT,
    charset: str = DEFAULT_CHARSET,
    label_sep: str | None = None,
    scale_edges: bool = False,
    weight_scale: float = 1.5,
    rankdir: str = "LR",
) -> str:
    """Return Graphviz DOT source for ``automaton``.

    Args:
        automaton: The automaton to draw.
        label_nodes: Whether to print state ids inside the nodes.
        fontname: The font Graphviz should use. The default has broad Unicode coverage;
            naming a font without the glyphs in use is what produces boxes.
        charset: The input encoding declared to Graphviz.
        label_sep: What to put between the tokens of a compacted transition. ``None``
            chooses per label: nothing between single characters, a space otherwise.
        scale_edges: Whether to vary edge thickness with the number of sequences running
            through each transition.
        weight_scale: How much thicker the busiest edge is than the thinnest, when
            ``scale_edges`` is set.
        rankdir: Graphviz layout direction.

    Returns:
        DOT source.

    Examples:
        >>> from dafsa import Dafsa
        >>> source = to_dot(Dafsa.from_sequences(["ab"]))
        >>> 'charset="UTF-8"' in source
        True
        >>> '"0" -> "1" [label="a"' in source
        True
    """
    widths = _pen_widths(automaton, weight_scale) if scale_edges else {}

    lines = [
        "digraph dafsa {",
        f'  graph [charset="{_escape(charset)}", rankdir="{_escape(rankdir)}", '
        f'fontname="{_escape(fontname)}"];',
        f'  node [fontname="{_escape(fontname)}", style="filled", fillcolor="white"];',
        f'  edge [fontname="{_escape(fontname)}"];',
    ]

    for state in automaton.states():
        attributes = [f'label="{state}"' if label_nodes else 'label=""']
        if state == ROOT:
            attributes.append('shape="doubleoctagon"')
        elif automaton.is_final(state):
            attributes.append('shape="doublecircle"')
        else:
            attributes.append('shape="circle"')
        lines.append(f'  "{state}" [{", ".join(attributes)}];')

    for state in automaton.states():
        for index in automaton.transition_indices(state):
            label = _escape(_join(automaton.transition_tokens(index), label_sep))
            attributes = [f'label="{label}"']
            if index in widths:
                attributes.append(f"penwidth={widths[index]:.2f}")
            target = automaton.transition_target(index)
            lines.append(f'  "{state}" -> "{target}" [{", ".join(attributes)}];')

    lines.append("}")

    return "\n".join(lines) + "\n"


def write_figure(
    automaton: Automaton,
    path: str | Path,
    *,
    dpi: int = 300,
    **dot_options: Any,
) -> None:
    """Render ``automaton`` to an image by invoking Graphviz.

    The output format is taken from the file extension.

    Args:
        automaton: The automaton to draw.
        path: Where to write. The suffix selects the format — ``.png``, ``.pdf``,
            ``.svg``, ``.dot`` and anything else Graphviz supports.
        dpi: Output resolution, where the format has one.
        **dot_options: Passed through to ``to_dot``.

    Raises:
        ExportError: If Graphviz is not installed, or if it fails.
        ValueError: If ``path`` has no extension to take a format from.
    """
    destination = Path(path)
    suffix = destination.suffix.lstrip(".")
    if not suffix:
        message = f"cannot infer an output format from {destination.name!r}"
        raise ValueError(message)

    source = to_dot(automaton, **dot_options)

    with tempfile.NamedTemporaryFile("w", suffix=".dot", encoding="utf-8", delete=False) as handle:
        handle.write(source)
        temporary = Path(handle.name)

    try:
        # Fixed argv, no shell, and both paths are ours.
        subprocess.run(
            [
                "dot",
                f"-T{suffix}",
                f"-Gdpi={dpi}",
                "-o",
                str(destination),
                str(temporary),
            ],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as error:
        message = (
            "Graphviz is required to write figures but the `dot` executable was "
            "not found; install Graphviz or use to_dot() and render elsewhere"
        )
        raise ExportError(message) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", "replace").strip()
        message = f"Graphviz failed to render {destination.name}: {detail}"
        raise ExportError(message) from error
    finally:
        temporary.unlink(missing_ok=True)


# -- networkx --------------------------------------------------------------


def to_networkx(automaton: Automaton) -> nx.MultiDiGraph:
    """Return ``automaton`` as a ``networkx`` graph.

    A ``MultiDiGraph``, for two reasons that 1.0 got wrong. It is
    **directed**, because an automaton is; ``nx.Graph`` discards the direction
    that makes it an automaton at all. And it is a **multigraph**, because two
    transitions may join the same pair of states, and a simple graph gives them
    one attribute slot to share, so one label silently overwrites the other.

    Args:
        automaton: The automaton to convert.

    Returns:
        Nodes carry ``final``, ``root`` and, when weighted, ``final_weight``.
        Edges carry ``label``, ``symbol``, ``tokens`` and ``weight``.

    Examples:
        >>> from dafsa import Dafsa
        >>> graph = to_networkx(Dafsa.from_sequences(["ab", "ac"]))
        >>> graph.is_directed(), graph.is_multigraph()
        (True, True)
        >>> graph.number_of_edges() == Dafsa.from_sequences(["ab", "ac"]).num_transitions
        True
    """
    graph = _networkx().MultiDiGraph()
    weighted = automaton.is_weighted

    for state in automaton.states():
        attributes: dict[str, Any] = {
            "final": automaton.is_final(state),
            "root": state == ROOT,
        }
        if weighted and automaton.is_final(state):
            attributes["final_weight"] = automaton.final_weight(state)
        graph.add_node(state, **attributes)

    for state in automaton.states():
        for index in automaton.transition_indices(state):
            tokens = automaton.transition_tokens(index)
            graph.add_edge(
                state,
                automaton.transition_target(index),
                label=_join(tokens, None),
                tokens=tokens,
                symbol=automaton.transition_symbol(index),
                weight=automaton.transition_weight(index),
            )

    return graph


def _flattened(automaton: Automaton) -> nx.MultiDiGraph:
    """Return a ``networkx`` graph whose attributes GML and GraphML accept.

    Both formats restrict attribute values to scalars, so tuples and semiring
    weights of arbitrary type are rendered as strings. Structure is untouched.
    """
    graph = to_networkx(automaton)

    for _, attributes in graph.nodes(data=True):
        attributes["final"] = str(attributes["final"])
        attributes["root"] = str(attributes["root"])
        if "final_weight" in attributes:
            attributes["final_weight"] = str(attributes["final_weight"])

    for _, _, attributes in graph.edges(data=True):
        attributes["tokens"] = _join(attributes["tokens"], " ")
        attributes["weight"] = str(attributes["weight"])

    return graph


def write_gml(automaton: Automaton, path: str | Path) -> None:
    """Write ``automaton`` to ``path`` in GML.

    Args:
        automaton: The automaton to write.
        path: Destination. Names ending in ``.gz`` or ``.bz2`` are compressed by
            ``networkx``.
    """
    _networkx().write_gml(_flattened(automaton), str(path))


def write_graphml(automaton: Automaton, path: str | Path) -> None:
    """Write ``automaton`` to ``path`` in GraphML.

    Args:
        automaton: The automaton to write.
        path: Destination.
    """
    _networkx().write_graphml(_flattened(automaton), str(path))


__all__ = [
    "DEFAULT_CHARSET",
    "DEFAULT_FONT",
    "to_dict",
    "to_dot",
    "to_json",
    "to_networkx",
    "write_figure",
    "write_gml",
    "write_graphml",
]
