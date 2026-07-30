"""Command-line interface.

Reads sequences, builds a structure, and writes it out in one of the export
formats.

The tokenization flag is the part worth reading carefully, because its absence is
what issue #17 was about. 1.0 took a ``delimiter`` argument that never split
anything — the library iterated a ``str`` character by character regardless —
while *this* program quietly called ``line.split()`` whenever it saw a space. So
the command line appeared to handle word tokens and the API did not, and the
difference was invisible from either side. Here the split is one flag, it does
nothing unless asked, and it is the same ``tokenize`` the API exposes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dafsa import __version__, export
from dafsa.alphabet import tokenize
from dafsa.semirings import BOOLEAN, COUNTING, LOG, PROBABILITY, TROPICAL, VITERBI
from dafsa.structures import Dafsa, Trie
from dafsa.suffix import SuffixAutomaton

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dafsa._types import Token
    from dafsa.automaton import Automaton
    from dafsa.semirings import Semiring


class _Characters:
    """Marks the default: no splitting, so a line is a sequence of characters."""

    __slots__ = ()


CHARACTERS = _Characters()

SEMIRINGS: dict[str, Semiring[Any]] = {
    "boolean": BOOLEAN,
    "counting": COUNTING,
    "tropical": TROPICAL,
    "log": LOG,
    "probability": PROBABILITY,
    "viterbi": VITERBI,
}

STRUCTURES = ("dafsa", "trie", "suffix")

FORMATS = ("text", "json", "dot", "gml", "graphml", "png", "pdf", "svg")

#: Formats that go through Graphviz rather than being written directly.
_RENDERED = ("png", "pdf", "svg")


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser.

    Returns:
        The parser, split out so that the options can be tested without running
        anything.
    """
    parser = argparse.ArgumentParser(
        prog="dafsa",
        description="Build a finite-state structure from sequences and export it.",
        epilog=(
            "Sequences are read one per line. By default each character is a "
            "token; pass --sep to split lines instead. With --structure suffix "
            "the whole input is indexed as one sequence."
        ),
    )
    parser.add_argument("source", help="file to read, or - for standard input")
    parser.add_argument("--version", action="version", version=f"dafsa {__version__}")

    shape = parser.add_argument_group("structure")
    shape.add_argument(
        "-f",
        "--structure",
        choices=STRUCTURES,
        default="dafsa",
        help="what to build (default: dafsa)",
    )
    shape.add_argument(
        "-s",
        "--semiring",
        choices=sorted(SEMIRINGS),
        default="boolean",
        help="the algebra weights belong to (default: boolean)",
    )
    # Two flags rather than one with an optional value: `--sep FILE` would
    # otherwise swallow the filename, since argparse cannot tell an omitted
    # optional value from the positional that follows it.
    tokens = shape.add_mutually_exclusive_group()
    tokens.add_argument(
        "--sep",
        metavar="SEP",
        help="split each line on SEP; without it, every character is a token",
    )
    tokens.add_argument(
        "--words",
        action="store_true",
        help="split each line on whitespace",
    )
    shape.add_argument(
        "--compact",
        action="store_true",
        help="collapse chains of states into compound transitions",
    )
    shape.add_argument(
        "--push",
        action="store_true",
        help="move weight towards the front (needs a divisible semiring)",
    )

    output = parser.add_argument_group("output")
    output.add_argument(
        "-t",
        "--to",
        choices=FORMATS,
        default="text",
        help="output format (default: text)",
    )
    output.add_argument(
        "-o", "--output", metavar="PATH", help="where to write (default: standard out)"
    )
    output.add_argument("--dpi", type=int, default=300, help="resolution for images")
    output.add_argument("--label-nodes", action="store_true", help="print state ids in the drawing")
    output.add_argument(
        "--font",
        default=export.DEFAULT_FONT,
        metavar="NAME",
        help=f"font for drawings (default: {export.DEFAULT_FONT})",
    )
    output.add_argument(
        "--label-sep",
        metavar="SEP",
        help="what to put between the tokens of a compound label",
    )
    output.add_argument(
        "--scale-edges",
        action="store_true",
        help="vary edge thickness with the number of sequences through them",
    )

    return parser


def read_sequences(source: str, separator: Any, *, single: bool) -> list[Sequence[Token]]:
    """Read sequences from a file or standard input.

    Args:
        source: A path, or ``-`` for standard input.
        separator: ``CHARACTERS`` to treat each character as a token, otherwise the
            separator handed to ``tokenize``.
        single: Whether to return the whole input as one sequence, which is what the
            substring index needs.

    Returns:
        The sequences.
    """
    text = sys.stdin.read() if source == "-" else Path(source).read_text("utf-8")
    lines = [line for line in text.splitlines() if line.strip()]

    if single:
        joined = "".join(lines) if separator is CHARACTERS else " ".join(lines)
        lines = [joined] if joined else []

    if separator is CHARACTERS:
        return [tuple(line) for line in lines]

    return [tokenize(line, separator) for line in lines]


def build(sequences: list[Sequence[Token]], options: argparse.Namespace) -> Automaton:
    """Build the requested structure.

    Args:
        sequences: The sequences to build from.
        options: Parsed arguments.

    Returns:
        The structure, compacted and pushed if asked.
    """
    semiring = SEMIRINGS[options.semiring]

    automaton: Automaton
    if options.structure == "suffix":
        automaton = SuffixAutomaton.from_sequence(
            sequences[0] if sequences else (), semiring=semiring
        )
    elif options.structure == "trie":
        automaton = Trie.from_sequences(sequences, semiring=semiring)
    else:
        automaton = Dafsa.from_sequences(sequences, semiring=semiring)

    if options.push:
        automaton = automaton.push()
    if options.compact:
        automaton = automaton.compact()  # type: ignore[attr-defined]

    return automaton


def describe(automaton: Automaton) -> str:
    """Return a readable summary of a structure.

    Args:
        automaton: The structure to describe.

    Returns:
        A few lines of counts.
    """
    lines = [
        f"{type(automaton).__name__} over {len(automaton.alphabet)} tokens",
        f"  states       {automaton.num_states}",
        f"  transitions  {automaton.num_transitions}",
        f"  sequences    {len(automaton)}",
    ]
    if automaton.is_weighted:
        lines.append(f"  total weight {automaton.total_weight()}")
        lines.append(f"  semiring     {type(automaton.semiring).__name__}")
    if automaton.is_compact:
        lines.append("  compacted    yes")

    return "\n".join(lines)


def write(automaton: Automaton, options: argparse.Namespace) -> None:
    """Write the structure in the requested format.

    Args:
        automaton: The structure to write.
        options: Parsed arguments.

    Raises:
        SystemExit: If a format that must be written to a file was given none.
    """
    drawing = {
        "label_nodes": options.label_nodes,
        "fontname": options.font,
        "label_sep": options.label_sep,
        "scale_edges": options.scale_edges,
    }

    if options.to in _RENDERED or options.to in {"gml", "graphml"}:
        if not options.output:
            message = f"--to {options.to} needs --output"
            raise SystemExit(message)
        if options.to in _RENDERED:
            export.write_figure(automaton, options.output, dpi=options.dpi, **drawing)
        elif options.to == "gml":
            export.write_gml(automaton, options.output)
        else:
            export.write_graphml(automaton, options.output)

        return

    if options.to == "text":
        text = describe(automaton)
    elif options.to == "json":
        text = export.to_json(automaton)
    else:
        text = export.to_dot(automaton, **drawing)

    if options.output:
        Path(options.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Argument vector to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        Process exit status.
    """
    options = build_parser().parse_args(argv)

    if options.sep == "":
        message = "--sep needs a separator; use --words to split on whitespace"
        raise SystemExit(message)

    separator: Any = CHARACTERS
    if options.words:
        separator = None
    elif options.sep is not None:
        separator = options.sep

    sequences = read_sequences(options.source, separator, single=options.structure == "suffix")
    write(build(sequences, options), options)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
