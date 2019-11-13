# encoding: utf-8

# Originally based on public domain code by Steve Hanov, published at
# http://stevehanov.ca/blog/?id=115

"""
Main module for computing DAFSA/DAWG graphs from list of strings.

Note that this is not intended from incremental use due to the assumption
that the list of strings can be sorted before computation.
"""

# TODO: Add support for tokens/ngrams, instead of only using characters
# TODO: rename the num_ methods to count_ ?
# TODO: comment all arguements, at least in this module
# TODO: check why root is not always sorted - or is sorted and we
#       just need to generate the label for it as well?

# Import Python libraries
import itertools

# Import other modules
from . import utils

# Define classes for DAFSA nodes and graphs
class DAFSANode:
    """
    Class rperesenting a node in the DAFSA.

    This class represents a node in the deterministic acyclic finite state
    automaton (DAFSA). It has a list of edges to other nodes. It has
    methods for testing whether it is equivalent to another node. Nodes are
    equivalent if they have identical edges, and each identical edge leads
    to identical states. The `__hash__()` and `__eq__()` methods allow it
    to be used as a key in a dictionary.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, node_id):
        self.node_id = node_id
        self.final = False
        self.edges = {}

    def __str__(self):
        """
        Return a textual representation of the node.

        The representation lists any edge, with `id` and `attr`ibute,
        and informs whether the node is marked as final or not. The
        edge dictionary is sorted at every call, so that, even if a bit
        more expansive computationally, the function is guaranteed to be
        idempotent.
        """

        arr = [
            "|".join([label, str(self.edges[label].node_id)])
            for label in sorted(self.edges)
        ]

        ret = ";".join(arr)

        if self.final:
            ret = "F(%s)" % ret
        else:
            ret = "n(%s)" % ret

        return ret

    def __eq__(self, other):
        """
        Checks whether two nodes are equivalent.

        Internally, the method reuses the `.__str__()` method, so that
        the logic for comparison is implemented in a single place.
        """

        return self.__str__() == other.__str__()

    def __gt__(self, other):
        """
        Compares two nodes for sorting purposes.

        Internally, the method reuses the `.__str__()` method, so that
        the logic for comparison is implemented in a single place.
        """

        return self.__str__() > other.__str__()

    def __hash__(self):
        """
        Returns a hash for the node, based on its string representation.
        """

        return self.__str__().__hash__()


class DAFSA:
    """
    Class representing a DAFSA graph.
    """

    def __init__(self):
        # Initializes an internal counter iterator, which is used to
        # provide IDs to nodes
        self._iditer = itertools.count()

        # List of nodes in the graph (during minimization, it is the list
        # of unique nodes that have been checked for duplicates).
        # Includes by default a root node
        self.root = DAFSANode(next(self._iditer))
        self.nodes = {}

        # Internal list of nodes that still hasn't been checked for
        # duplicates; note that the data structure, a list of
        # parent, attribute, and child, is different from the result
        # stored in `self.nodes` after minimization
        self._unchecked_nodes = []

        # Variable holding the number of sequences stores; it is initialized
        # to `None`, so we can differentiate from empty sets. Note that it
        # set as an internal variable, to be accessed with the
        # `.num_sequences()` method in analogy to the number of nodes and
        # edges.
        self._num_sequences = None

    # TODO: allow to override minimization?
    def insert(self, sequences):
        """
        Insert a list of sequences to the structure and finalizes it.
        """

        # Take a sorted set of the sequences and store its number
        sequences = sorted(set(sequences))
        self._num_sequences = len(sequences)

        # Make sure the words are sorted and add a dummy empty previous
        # word for the loop
        for previous_seq, seq in utils.pairwise([""] +sequences):
            self._insert_single_seq(seq, previous_seq)

        # Minimize the entire graph, no restrictions, so that we clean
        # `self._unchecked_nodes`
        self._minimize()

    def _insert_single_seq(self, seq, previous_seq):
        # Obtain the length of the common_prefix between the current word
        # and the one added before it, then using ._unchecked_nodes for
        # removing redundant nodes, proceeding from the last one down to
        # the the common prefix size. The list will be truncated at that
        # point.
        prefix_len = utils.common_prefix_length(seq, previous_seq)
        self._minimize(prefix_len)

        # add the suffix, starting from the correct node mid-way through the
        # graph, provided there are unchecked nodes (otherwise, just
        # start at the root)
        if not self._unchecked_nodes:
            node = self.root
        else:
            node = self._unchecked_nodes[-1][2]

        # For everything after the common prefix, create as many necessary
        # new nodes and add them.
        for token in seq[prefix_len:]:
            # Create a new child node, build an edge to it, add it to the
            # list of unchecked nodes (there might be duplicates in the
            # future) and proceed until the end of the sequence
            child = DAFSANode(next(self._iditer))
            node.edges[token] = child
            self._unchecked_nodes.append([node, token, child])
            node = child

        # This last node from the above loop is a terminal one
        node.final = True

    def _minimize(self, index=0):
        # minimize the graph from the last unchecked item to `index`;
        # final minimization, the default, traverses the entire data
        # structure.

        # Please note that this loop could be removed, but it would
        # unnecessarily complicate a logic which is already not immediately
        # intuite (even if less idiomatic). Also note that, to guarantee
        # that the graph is minimized as much as possible with a single
        # call to this method, we restart the loop each time an item is
        # changed, only leaving when it is untouched.
        while True:
            # Sentinel to whether the graph was changed
            graph_changed = False

            for _ in range(len(self._unchecked_nodes) - index):
                # Remove the last item from unchecked nodes and extract
                # information on parent, attribute, and child for checking
                # if we can minimize the graph.
                parent, token, child = self._unchecked_nodes.pop()

                # If the child is already among the minimized nodes, replace it
                # with one previously encountered, also setting the sentinel;
                # otherwise, add the state to the list of minimized nodes.
                if child in self.nodes:
                    parent.edges[token] = self.nodes[child]
                    graph_changed = True
                else:
                    self.nodes[child] = child

            # Only leave the loop if the graph was untouched
            if not graph_changed:
                break

    def lookup(self, seq):
        """
        Checks if a sequence is expressed by the graph.

        Return False if not included, and a reference to the final node
        otherwise.
        """

        # Start at the root
        node = self.root

        # If we can follow a path, it is valid, otherwise return false
        for token in seq:
            if token not in node.edges:
                return False
            node = node.edges[token]

        return node

    def num_nodes(self):
        """
        Returns the number of minimized nodes in the structure.
        """

        return len(self.nodes)

    def num_edges(self):
        """
        Returns the number of minimized edges in the structure.
        """

        return sum([len(node.edges) for node in self.nodes])

    def num_sequences(self):
        """
        Returns the number of sequences the structure.
        """

        return self._num_sequences

    def __str__(self):
        """
        Returns a readable, multiline textual representation.
        """

        # Add basic statistics
        # TODO: add number of sequences
        buf = [
            "DAFSA with %i nodes and %i edges (%i sequences)"
            % (self.num_nodes(), self.num_edges(), self.num_sequences())
        ]

        # Add information on root node
        # TODO: move root to general nodes?
        buf += [
            "+-- ROOT %s %s"
            % (
                [self.root.node_id],
                [
                    (label, n.node_id)
                    for label, n in self.root.edges.items()
                ],
            )
        ]

        # Add information on nodes
        # TODO: better sorting
        for node in sorted(self.nodes):
            buf += [
                "    +-- %s %s %s"
                % (
                    node,
                    [node.node_id],
                    [
                        (label, n.node_id)
                        for label, n in node.edges.items()
                    ],
                )
            ]

        # build a single string and returns
        return "\n".join(buf)

    # TODO: add terminals
    def to_dot(self):
        dot_edges = []

        # add root edges
        for attr, node in self.root.edges.items():
            buf = '"root" -> "%i" [label="%s"] ;' % (node.node_id, attr)
            dot_edges.append(buf)

        # add other edges
        for left in self.nodes:
            for attr, right in left.edges.items():
                buf = '"%i" -> "%i" [label="%s"] ;' % (left.node_id,
                right.node_id, attr)
                dot_edges.append(buf)

        # build dot
        source = """
digraph G {
graph [layout="dot",rankdir="LR"];
%s
}
""" % "\n".join(dot_edges)

        return source
