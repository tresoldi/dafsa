"""Redraw ``figures/trie-vs-dafsa.png``, the figure the README opens with.

The two automata are emitted by :mod:`dafsa.export` and stitched into one
Graphviz source with a cluster each, so the picture is the library's own output
rather than a hand-drawn approximation of it. Run with::

    python figures/trie-vs-dafsa.py

Graphviz must be installed and ``dot`` on the path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dafsa import Dafsa, Trie
from dafsa.export import to_dot

if TYPE_CHECKING:
    from dafsa.automaton import Automaton

WORDS = ["tap", "taps", "top", "tops"]
OUTPUT = Path(__file__).resolve().parent / "trie-vs-dafsa.png"


def cluster(automaton: Automaton, name: str, title: str) -> str:
    """Return ``automaton``'s DOT body wrapped in a titled cluster.

    State ids are namespaced with ``name`` so the two automata can share one
    graph without colliding.

    Args:
        automaton: The automaton to draw.
        name: A prefix, unique within the figure.
        title: The cluster's caption.

    Returns:
        The cluster, as DOT source.
    """
    body = [
        line
        for line in to_dot(automaton).splitlines()[1:-1]
        if not line.lstrip().startswith(("graph [", "node [", "edge ["))
    ]
    renamed = [line.replace('"', f'"{name}', 1).replace('" -> "', f'" -> "{name}') for line in body]

    return "\n".join(
        [
            f"  subgraph cluster_{name} {{",
            f'    label="{title}";',
            '    labelloc="b";',
            '    color="#d8d8d8";',
            '    fontsize="18";',
            *(f"  {line}" for line in renamed),
            "  }",
        ]
    )


def main() -> None:
    """Write the figure."""
    source = "\n".join(
        [
            "digraph dafsa {",
            '  graph [charset="UTF-8", rankdir="LR", fontname="DejaVu Sans"];',
            '  node [fontname="DejaVu Sans", style="filled", fillcolor="white"];',
            '  edge [fontname="DejaVu Sans"];',
            # Graphviz stacks clusters bottom-up under rankdir="LR", so the one
            # meant to appear on top is emitted last.
            cluster(Dafsa.from_sequences(WORDS), "dafsa", "DAFSA — 5 states"),
            cluster(Trie.from_sequences(WORDS), "trie", "Trie — 8 states"),
            "}",
        ]
    )
    subprocess.run(
        ["dot", "-Tpng", "-Gdpi=150", "-o", str(OUTPUT)],
        input=source,
        text=True,
        check=True,
    )
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
