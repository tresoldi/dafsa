import pathlib
import subprocess
import tempfile
from collections import namedtuple
from typing import List, Optional

RESOURCE_DIR = pathlib.Path(__file__).parent.parent.parent / "resources"


# TODO: return type
def extract_sequences(
    array: List[namedtuple], node_idx: Optional[int] = None, carry=""
):
    # Obtain the root node, defaulting to the last one
    if node_idx is None:
        node_idx = array[-1].child

    node = array[node_idx]

    # TODO: necessary when moving to sequences of arbitrary elements?
    if not node.value:
        return

    # Recursively build all sequences
    while True:
        for ret in extract_sequences(array, node.child, carry + node.value):
            yield ret

        # If we hit a terminal node, just yield what was carried plus the current value
        if node.terminal:
            yield carry + node.value

        # If we are at a group end, just break out of the `while True` group
        if node.group_end:
            break

        # Move to the next node in the group
        node_idx += 1
        node = array[node_idx]


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


def read_words(filename):
    lines = open(filename, encoding="utf-8").readlines()
    lines = [line.strip() for line in lines]
    if " " in lines[0]:
        lines = tuple([tuple(w.split()) for w in lines])

    return tuple(lines)
