from collections import namedtuple
from typing import Hashable, List, Optional

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


def read_words(filename):
    lines = open(filename, encoding="utf-8").readlines()
    lines = [line.strip() for line in lines]
    if " " in lines[0]:
        lines = tuple([tuple(w.split()) for w in lines])

    return tuple(lines)
