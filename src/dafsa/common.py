"""
Common functions and variables.
"""

# Import Python standard libraries
import pathlib
import subprocess
import tempfile
from typing import Hashable, Optional, Sequence, Tuple

# Import from other modules
from .dafsaarray import extract_sequences
from .minimize import minimize_trie
from .node import Node


def build_dafsa(sequences: Sequence[Sequence[Hashable]], check: bool = False):
    """
    Build a DAFSA object from a collection of sequences.

    This is the "main" function of the library, and the one that will be most
    used by users.

    :param sequences: The collection of sequences to be used
        to build the DAFSA object.
    :param check: Whether to run a check to verify whether the set of
        sequences returned by the DAFSA matches the input.
    :return: The DAFSA object minimizing the sequences.
    """

    # Build trie, pointing to the root node, and minimize it
    root_node = Node(sequences)
    array = minimize_trie(root_node)

    # Check correctness if requested
    if check:
        if set(extract_sequences(array)) != set(sequences):
            raise ValueError("DAFSA is expressing a different set of sequences.")

    #    import matplotlib.pyplot as plt
    #    import networkx as nx

    #    G = array.to_graph()
    #    edge_labels = nx.get_edge_attributes(G, "label")
    #    formatted_edge_labels = {
    #        (elem[0], elem[1]): edge_labels[elem] for elem in edge_labels
    #    }

    #    pos = nx.spring_layout(G)
    #    nx.draw_networkx(G, arrows=True, with_labels=True, node_color="skyblue", pos=pos)
    #    nx.draw_networkx_edge_labels(
    #        G, pos, edge_labels=formatted_edge_labels, font_color="red"
    #    )
    #    plt.show()

    # dot = array.to_dot()
    #    graphviz_output(dot, "temp.png")

    return array


def graphviz_output(
    dot_source: str, output_file: str, dpi: int = 300
) -> subprocess.CompletedProcess:
    """
    Generates a visualization by calling the local `graphviz`.

    The filetype will be decided from the extension of the `filename`.

    :param dot_source: The DOT source to be compiled by GraphViz.
    :param output_file: The path to the output file.
    :param dpi : The output resolution, if applicable. Defaults to 300.
    :return: A `CompleteProcess` instance, as returned by the `subprocess` call.
    """

    # Write to a named temporary file so we can call `graphviz`
    handler = tempfile.NamedTemporaryFile()
    handler.write(dot_source.encode("utf-8"))
    handler.flush()

    # Get the filetype from the extension and call graphviz
    suffix = pathlib.PurePosixPath(output_file).suffix
    ret = subprocess.run(
        [
            "dot",
            "-T%s" % suffix[1:],
            "-Gdpi=%i" % dpi,
            "-o",
            output_file,
            handler.name,
        ],
        check=True,
        shell=False,
    )

    # Close the temporary file
    handler.close()

    return ret


def read_words(
    filename: str, delimiter: Optional[str] = None, encoding: str = "utf-8"
) -> Tuple[Tuple[str]]:
    """
    Auxiliary function for reading textual lists of sequences.

    The function assumes there file holds one sequence per line. An optional
    `delimiter` might be provided, indicating the string the delimits
    the tokens of each sequence (usually, if used, a space or an
    underscore). If not provided, the function assumes that each character
    constitutes an independent token.

    :param filename: The source file.
    :param encoding: The encoding of the source file (defaults to `utf-8`).
    :param delimiter: An optional string to be used as in-sequence
        delimiter.
    :return: A collection of the sequences.
    """

    lines = open(filename, encoding=encoding).readlines()
    seqs = [line.strip() for line in lines]

    # Split data into tokens if delimiters are found
    if delimiter:
        delims = any([delimiter in seq for seq in seqs])
    else:
        delims = False

    if delims:
        seqs = [tuple(seq.split()) for seq in seqs]
    else:
        seqs = [tuple([char for char in seq]) for seq in seqs]

    return tuple(seqs)
