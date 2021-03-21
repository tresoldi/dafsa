# Import Python standard libraries
from collections import defaultdict, namedtuple
from copy import copy, deepcopy
from typing import Dict, Hashable, List, Optional, Tuple

# Import from other modules
from .searchgraph import SearchGraph

# TODO: have __all__? Or let __init__ specify?
# TODO: minimization -> compression

# Define the NamedTuple for the compressed array (see comments at the end of
# `build_compression_array()`).
ArrayEntry = namedtuple("ArrayEntry", ["value", "group_end", "terminal", "child"])

# TODO: Rename `trie` to `root node`?
def merge_redundant_nodes(
    trie: SearchGraph,
) -> Dict[Tuple[SearchGraph, ...], Tuple[SearchGraph, ...]]:
    """
    Build a dictionary with information for merging redundant nodes.

    This function is the core of the compression method, using single references ("hashes") to identify
    common paths, as in the reference implementation. Note that the "hashing" function is not called at
    each request, but its value is stored as a reference value in the object itself. This is done both
    for speed (no need to recompute) and to follow the logic, inherited from the original C
    implementation, where objects are mutable and are manipulated, meaning that subsequent calls
    to the same object could find a different status leading, as expected, to a different "hash".

    The `hashing` function is actually, in this Python implementation, a tuple representation
    provided by `._internal_repr()`, which, among other advantages, is more easily debuggable and
    guarantees reproducibility (as Python hashes are, by security design, not reproducible).

    *Note*: This function does not preserve the values and structure of the original graph, by design.
    If these are necessary, the user must pass a deep-copy.

    :param trie: The root node of the graph ("trie") to be reduced.
    :return: A dictionary with the redundant tuples of nodes.
    """

    # Build node dictionary
    node_dict = {}
    for node in trie:
        node.stable_ref = node._internal_repr()
        if node.stable_ref not in node_dict:
            node_dict[node.stable_ref] = node
            node.children = [
                node_dict[child_node.stable_ref] for child_node in node.children
            ]

        node.children = tuple(sorted(node.children))

    # Build dictionary of children lists: we start with a children pointing to
    # itself and then have the node children point to what is pointed in
    # the dictionary
    clist_dict = {node.children: node.children for node in node_dict.values()}
    for node in node_dict.values():
        node.children = clist_dict[node.children]

    return clist_dict


def merge_child_list(
    clist_dict: Dict[Tuple[SearchGraph, ...], Tuple[SearchGraph, ...]]
) -> Dict[Tuple[SearchGraph], List[Tuple[SearchGraph]]]:
    """
    Merges the children in a child list, preparing for a minimized array.

    :param clist_dict: A dictionary with the redundant tuples of nodes, as returned
        by `merge_redundant_nodes()`.
    :return: A reduced version of `clist_dist` with merged nodes.
    """

    # Initialize `inverse_dict` and `compress_dict`; the latter starts as a dictionary of keys and
    # lists with pointing to themselves (`compress_dict[x] = [x]`), the first is just for inverse
    # lookup from each `node` to all `clist`s pointing to that node
    inverse_dict = defaultdict(list)
    compress_dict = {}
    for clist in clist_dict.values():
        if clist:
            compress_dict[clist] = [clist]
            for node in clist:
                inverse_dict[node].append(clist)

    # Sort node tries in `inverse_dict` by length first and, if necessary, by the sum of occurrences in
    # the whole dictionary, so that complexity is pushed to the end of the list
    for node in inverse_dict:
        inverse_dict[node].sort(
            key=lambda _trie: (
                len(_trie),
                sum(len(inverse_dict[_trie_node]) for _trie_node in _trie),
            )
        )

    # Obtain a sorted list of `clists` (from the compression dictionary) and iterate over them; note that
    # the sorting logic is essentially the same as above, but the list is reserved (from the most complex to
    # the simplest)
    clist_sorted = sorted(
        compress_dict.keys(),
        key=lambda _trie: (
            len(_trie),
            -1 * sum(len(inverse_dict[n]) for n in _trie),
        ),
        reverse=True,
    )

    for clist in clist_sorted:
        for other in min((inverse_dict[t] for t in clist), key=len):
            if compress_dict[other] and set(clist) < set(compress_dict[other][-1]):
                compress_dict[other].append(clist)
                compress_dict[clist] = None
                break

    # Build the return dictionary with tries and what they compress to; `target` can be `None`, as
    # attributed above, meaning the edge will be dropped
    return {_trie: target for _trie, target in compress_dict.items() if target}


# TODO; rename `trie` to `root?
def build_compression_array(
    trie: SearchGraph, compress_dict: Dict[Tuple[SearchGraph], List[Tuple[SearchGraph]]]
) -> List[namedtuple]:
    """
    Build a compression array used for building graphs and other output.

    :param trie: The root node of the graph to be compressed.
    :param compress_dict: The compression dictionary listing children to be merged, as provided
        by `merge_child_list()`.
    :return: The ordered list of elements that make up the array.
    """

    # Initialize compression array
    array_length = sum(len(_trie[0]) for _trie in compress_dict.values())
    array: List[Optional[SearchGraph]] = [None] * array_length

    # Insert the first element of the array as the common end node
    end_node = SearchGraph(group_end=True)
    end_node.children = ()  # make sure it is a tuple for hashing TODO: fix this
    array.insert(0, end_node)

    # Collect all unique elements in a sorted list, so that we can set the positions in
    # the array
    elements = sorted(set(trie.collect_elements()))
    element_idx: Dict[Hashable, int] = {
        element: idx for idx, element in enumerate(elements)
    }

    # Initialize the `clist_indices` dictionaries, with the empty tuple in first position (zero) and the first
    # position available (`pos`) as 1 and iterate over all values in the compressed dictionary
    clist_indices = {(): 0}
    pos = 1
    for trie_list in compress_dict.values():
        # If there is a single element, it goes to position; otherwise, add all them
        if len(trie_list) == 1:
            clist_indices[trie_list[0]] = pos
        else:
            sort_array = [None] * len(elements)
            for i, clist in enumerate(trie_list):
                for y in clist:
                    sort_array[element_idx[y.value]] = (i, y)

            trie_list.append([n for _, n in sorted(x for x in sort_array if x)])
            for clist in trie_list[:-1]:
                clist_indices[clist] = pos + len(trie_list[0]) - len(clist)

        # Update the array, also offsetting `pos` as much as necessary and setting `group_end`
        clist = trie_list[-1]
        array[pos : pos + len(clist)] = map(copy, clist)
        pos += len(clist)
        array[pos - 1].group_end = True

    # Update `clist_indices` for all children in all nodes
    for node in array:
        node.children = clist_indices[node.children]

    # Build root node and append it to the end of the array
    root_node = SearchGraph(group_end=True)
    root_node.children = clist_indices[trie.children]
    array.append(root_node)

    # At this point, `array` is a list of nodes where we don't obey the `.children` type (a list
    # of other nodes), as they now point to the index in the array itself. This should be
    # an obvious inheritance from C to everybody (they were originally pointers), and while
    # I can be "excused" for doing that when computing the compression array, as the solution is
    # also fast, we should not let this propagate to outside the function. Thus, here I
    # build the actual list of dictionaries that is returned, with plain information.
    # TODO: Here using named tuples because of Python3.6 support; move to data classes in the future.
    ret = [
        ArrayEntry(entry.value, entry.group_end, entry.terminal, entry.children)
        for entry in array
    ]

    return ret


def minimize_trie(trie: SearchGraph) -> List[namedtuple]:
    """
    Higher level function to minimize a trie.

    :param trie: The trie to be compressed.
    :return: A list of ArrayEntries with the information to build a compressed
        graph. Each entry informs the node `value`, whether it is a `group_end`,
        whether it is a `terminal`, and a pointer to the `child` in the list.
        The last item is the starting node pointing to the root(s).
    """

    # Make a copy of the trie, as it is not preserved during minimization
    # TODO: can use `copy`? should be a method of itself?
    trie_copy = deepcopy(trie)

    # Merge redundant nodes with "hashes"
    clist_dict = merge_redundant_nodes(trie_copy)

    # Merge child lists
    compress_dict = merge_child_list(clist_dict)

    # Create compressed trie structure
    array = build_compression_array(trie_copy, compress_dict)

    return array
