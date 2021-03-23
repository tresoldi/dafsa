"""
Common functions and variables.
"""

# Import Python standard libraries
import pathlib
import subprocess
import tempfile
from typing import Hashable, Iterator, List, Optional, Tuple

# Import from other modules
from .minimize import DafsaArray

# TODO: move to the array
def extract_sequences(
    array: DafsaArray, node_idx: Optional[int] = None, carry: Optional[Tuple] = None
) -> Iterator[List[Hashable]]:
    """
    Build an iterator with the sequences included in an array.

    :param array: The array from where to extract the sequences.
    :param node_idx: The index of the node to serve as root; if not
        provided, will start from the last one (holding the actual
        graph root).
    :param carry: Information carried from the path, used by the
        method recursively.
    :return: The sequences expressed by the automaton.
    """

    # Obtain the root node, defaulting to the last one
    if node_idx is None:
        node_idx = array.entries[-1].child

    node = array.entries[node_idx]

    # Quit if we hit an empty node; we cannot check for .terminal, as by definition
    # in a DAFSA a terminal might be continued. This excludes having empty nodes
    # in the middle of the sequence.
    # TODO: update code in addition to have the check as `is None`
    if not node.value:
        return

    # Recursively build all sequences
    while True:
        if not carry:
            sub_seq = (node.value,)
        else:
            sub_seq = carry + (node.value,)

        for ret in extract_sequences(array, node.child, sub_seq):
            yield ret

        # If we hit a terminal node, just yield what was carried plus the current value
        if node.terminal:
            yield sub_seq

        # If we are at a group end, just break out of the `while True` group
        if node.group_end:
            break

        # Move to the next node in the group
        node_idx += 1
        node = array.entries[node_idx]


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

    :param filename:
    :param encoding:
    :param delimiter:
    :return:
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
