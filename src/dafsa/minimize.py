# Import Python standard libraries
from collections import defaultdict, namedtuple
from copy import copy, deepcopy
from typing import Dict, Hashable, List, Optional, Tuple

# Import 3rd-party libraries
import networkx as nx

# Import from other modules
from .searchgraph import SearchGraph
from .common import RESOURCE_DIR

# TODO: have __all__? Or let __init__ specify?
# TODO: minimization -> compression?
# TODO: add compression as binary array (load and save?)
# TODO: add weights

# Define the NamedTuple for the elements of a compressed array (see comments at
# the end of `build_compression_array()`).
ArrayEntry = namedtuple(
    "ArrayEntry", ["value", "group_end", "terminal", "child", "weight"]
)


class DafsaArray:
    """
    Class for representing and operating compressed arrays representing dafsas.
    """

    def __init__(self, entries: List[ArrayEntry]):
        # TODO; rename to elements, or nodes
        self.entries = entries

    def show(self):
        print("Number of nodes:", len(self))

        for idx, node in enumerate(self.entries):
            print(idx, node.value, node.group_end, node.terminal, node.child)

    def to_dot(self, label_nodes: bool = False, weight_scale: float = 1.5) -> str:
        """
        Return a representation of the DAFSA as a .dot (Graphviz) source code.

        :param label_nodes: A boolean flag indicating whether or not to label
            nodes with their respective node ids (default: `False`).
        :param weight: A floating point value indicating how much edges in
            the graph should be scaled in relation to their frequency
            (default: `1.5`).
        :return: The .DOT source code representing the DAFSA.
        """

        # collect the maximum node weight for later computing the size
        max_weight = max([node.weight for node in self.entries])

        # collect all nodes
        dot_nodes = []
        for node_id, node in enumerate(self.entries):
            # List for collecting node attributes
            node_attr = []

            # Decide on node label
            if label_nodes:
                node_attr.append('label="%i"' % node_id)
            else:
                node_attr.append('label=""')

            # Decide on node shape
            if node_id == len(self.entries) - 1:
                node_attr.append('shape="doubleoctagon"')
            elif node.terminal:
                node_attr.append('shape="doublecircle"')
            else:
                node_attr.append('shape="circle"')

            # Set node size
            node_attr.append("width=%.2f" % ((1.0 * (node.weight / max_weight)) ** 0.5))

            # All nodes as filled
            node_attr.append('style="filled"')

            # Build the node attributes string
            buf = '"%i" %s ;' % (node_id, "[%s]" % ",".join(node_attr))
            dot_nodes.append(buf)

        # add other edges
        # TODO: almost same logic of to_graph(), should merge
        dot_edges = []

        # List of nodes indices that were visited when building the graph, and to visit (starting with the
        # last node in the list)
        visited = []
        to_visit = [len(self) - 1]

        while to_visit:
            node_idx = to_visit.pop()

            # Add to list of visited nodes
            visited.append(node_idx)

            # Obtain the pointer to the first node of the children group
            ptr = self.entries[node_idx].child

            # Collect all children indexes by checking `group_end`
            while True:
                buf = '"%i" -> "%i" [label="%s",penwidth=%i] ;' % (
                    node_idx,
                    ptr,
                    self.entries[ptr].value,
                    self.entries[ptr].weight * weight_scale,
                )
                dot_edges.append(buf)

                if ptr not in visited:
                    to_visit.append(ptr)

                if self.entries[ptr].group_end:
                    break
                else:
                    ptr += 1

        # load template and build .dot source
        template = RESOURCE_DIR / "template.dot"
        with open(template.as_posix()) as handler:
            source = handler.read()

        source = source.replace("$dot_nodes$", "\n".join(dot_nodes))
        source = source.replace("$dot_edges$", "\n".join(dot_edges))

        return source

    def to_graph(self) -> nx.Graph:
        """
        Return a `networkx` graph for the DAFSA based on the current array.

        :return: The DAFSA as a `networkx` graph object.
        """
        graph = nx.Graph()

        # List of nodes indices that were visited when building the graph, and to visit (starting with the
        # last node in the list)
        visited = []
        to_visit = [len(self) - 1]

        while to_visit:
            node_idx = to_visit.pop()

            # Add to list of visited nodes
            visited.append(node_idx)

            # Obtain the pointer to the first node of the children group
            ptr = self.entries[node_idx].child

            # Collect all children indexes by checking `group_end`
            while True:
                graph.add_edge(
                    node_idx,
                    ptr,
                    label=self.entries[ptr].value,
                    terminal=self.entries[ptr].terminal,
                )

                if ptr not in visited:
                    to_visit.append(ptr)

                if self.entries[ptr].group_end:
                    break
                else:
                    ptr += 1

        return graph

    def write_gml(self, filename: str):
        """
        Write the DAFSA in GML format to the file `filename`.

        :param filename: The filename to write. Files whose names end with .gz or
            .bz2 will be compressed.
        """

        nx.readwrite.gml.write_gml(self.to_graph(), filename)

    def __len__(self) -> int:
        return len(self.entries)

    def __hash__(self) -> int:
        return hash(self.entries)


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
) -> List[ArrayEntry]:
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
    # Note that weight is set to 1.0 here in all cases.
    # TODO: deal with weight
    # TODO: Here using named tuples because of Python3.6 support; move to data classes in the future.
    ret = [
        ArrayEntry(entry.value, entry.group_end, entry.terminal, entry.children, 1.0)
        for entry in array
    ]

    return ret


def minimize_trie(trie: SearchGraph) -> DafsaArray:
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
    entries = build_compression_array(trie_copy, compress_dict)
    array = DafsaArray(entries)

    return array
