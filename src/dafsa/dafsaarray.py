# Import Python standard libraries
from collections import namedtuple
from typing import List
from pathlib import Path

# Import 3rd-party libraries
import networkx as nx

# TODO: add compression as binary array (load and save?)

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
        :param weight_scale: A floating point value indicating how much edges in
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
        template = Path(__file__).parent / "template.dot"
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
