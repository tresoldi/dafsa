# encoding: utf-8

# Originally based on public domain code by Steve Hanov, published at
# http://stevehanov.ca/blog/?id=115

"""
Main module for computing DAFSA/DAWG graphs from list of strings.

Note that this is not intended from incremental use due to the assumption
that the list of strings can be sorted before computation.
"""

# Import Python libraries
from collections import Counter
import copy
import itertools

# Import 3rd party libraries
import networkx as nx

# Import other modules
from . import output
from . import utils

# comment on internal node_id, meaningless
class DAFSANode:
    """
    Class representing a node in the DAFSA.

    This class represents a node in the deterministic acyclic finite state
    automaton (DAFSA). It carries a `node_id` which must be globally unique
    in the graph, a list of edges the node points to, and information on
    whether the node can be final. For matters of minimization, nodes are
    considered equivalent (as per the `.__eq__()` method) if they have
    identical edges, with each edge pointing to the same node (edge count
    and final state are *not* considered). The `.__hash__()` method allows
    to use a DAFSANode as a dictionary key.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, node_id):
        """
        Initializes a DAFSANode.

        Parameters
        ----------
        node_id : int
            The global unique ID for the current node.
        """

        # Set values; by default, we start with empty (no edges) and
        # non-final nodes
        self.node_id = node_id
        self.edges = {}
        self.final = False
        self.weight = 0

    def __str__(self):
        """
        Return a textual representation of the node.

        The representation lists any edge, with `id` and `attr`ibute. The
        edge dictionary is sorted at every call, so that, even if a bit
        more expansive computationally, the function is guaranteed to be
        idempotent in all implementations.

        Please note that, as counts and final state are not accounted for,
        the value returned by this method might be ambiguous, with different
        nodes returning the same value. For unambigous representation,
        the `.__repr__()` method must be used.
        """

        buf = ";".join(
            [
                "|".join([label, str(self.edges[label].node.node_id)])
                for label in sorted(self.edges)
            ]
        )

        return buf

    def __repr__(self):
        """
        Return an unambigous textual representation of the node.

        The representation lists any edge, with all properties. The
        edge dictionary is sorted at every call, so that, even if a bit
        more expansive computationally, the function is guaranteed to be
        idempotent in all implementations.

        Please note that, as the return value includes information such as
        edge weight, it cannot be used for minimization. For such purposes,
        the potentially ambiguous `.__str__()` method must be used.
        """

        buf = ";".join(
            [
                "|".join(
                    [
                        "#%i/%i:<%s>/%i"
                        % (
                            self.edges[label].node.node_id,
                            self.weight,
                            label,
                            self.edges[label].weight,
                        )
                        for label in sorted(self.edges)
                    ]
                )
            ]
        )

        if self.node_id == 0:
            buf = "0(%s)" % buf
        elif self.final:
            buf = "F(%s)" % buf
        else:
            buf = "n(%s)" % buf

        return buf

    def __eq__(self, comp):
        """
        Checks whether two nodes are equivalent.

        Please note that this method checks for *equivalence* (in particular,
        disregarding edge weight), and not for *equality*. Internally,
        it reuses the `.__str__()` method, so that the logic for comparison
        is implemented in a single place.
        """

        return str(self) == str(comp)

    def __gt__(self, other):
        """
        Compares two nodes for sorting purposes.

        Internally, the method reuses the `.__str__()` method, so that
        the logic for comparison is implemented in a single place. Note that,
        currently, this only guarantees that the sorting will always
        return the same sorted items, without an actual basis on "length"
        or "information amount" (which would need to be decided).
        """

        return self.__str__() > other.__str__()

    def __hash__(self):
        """
        Returns a hash for the node, based on its string representation.
        """

        return self.__str__().__hash__()


class DAFSAEdge(dict):
    """
    Class representing an edge in the DAFSA.
    """

    def __init__(self, node, weight=0):
        """
        Initializes a DAFSA edge.

        Parameters
        ----------
        node : DafsaNode
            Reference to the target node, mandatory.
        weight : int
            Edge weight as collected from training data. Defaults to 0.
        """

        # Call super class initialization.
        # This class currently works as a simple dictionary, but it is already
        # implemented as a class to allow easy future expansions, particularly
        # for implementing fuzzy automata.
        super().__init__()

        # Validate values and set
        if not isinstance(node, DAFSANode):
            raise TypeError(
                "`node` must be a DAFSANode (perhaps a node_id was passed?)."
            )
        self.node = node
        self.weight = weight

    def __str__(self):
        return "{node_id: %i, weight: %i}" % (self.node.node_id, self.weight)


class DAFSA:
    """
    Class representing a DAFSA graph.
    """

    def __init__(self, sequences=None, **kwargs):
        """
        Initializes a DAFSA object.

        Parameters
        ----------
        sequences : list
            List of sequences to be added to the DAFSA from initialization.
            Defaults to `None`.
        minimize : bool
            Whether to run the minimization or not in case `sequences` are
            provided. Defaults to `True`.
        weight : bool
            Whether to collect edge weights after minimization. Defaults
            to `True`.
        join_trans: bool
            Whether to join sequences of transitions into single compound
            transitions when possible. Defaults to `False`.
        """

        # Initializes an internal counter iterator, which is used to
        # provide unique IDs to nodes
        self._iditer = itertools.count()

        # List of nodes in the graph (during minimization, it is the list
        # of unique nodes that have been checked for duplicates).
        # Includes by default a root node. We also initialize to `None`
        # the .lookup_nodes property, which is used mostly by .lookup
        # and will be equivalent to .nodes if no single path joining is
        # performed
        self.nodes = {0: DAFSANode(next(self._iditer))}
        self.lookup_nodes = None

        # Internal list of nodes that still hasn't been checked for
        # duplicates; note that the data structure, a list of
        # parent, attribute, and child, is different from the result
        # stored in `self.nodes` after minimization
        self._unchecked_nodes = []

        # Variable holding the number of sequences stores; it is initialized
        # to `None`, so we can differentiate from empty sets. Note that it
        # is set as an internal variable, to be accessed with the
        # `.num_sequences()` method in analogy to the number of nodes and
        # edges.
        self._num_sequences = None

        # Store information on single transition joining (`join_trans`)
        # and corresponding `delimiter` which are needed, in case of
        # single transition joining, by the `.lookup` method.
        self._join_trans = kwargs.get("join_trans", False)
        self._delimiter = kwargs.get("delimiter", None)

        # Insert the sequences, if provided
        if sequences:
            self.insert(sequences, **kwargs)

    def insert(self, sequences, **kwargs):
        """
        Insert a list of sequences to the structure and finalizes it.

        Parameters
        ----------
        sequences : list
            List of sequences to be added to the DAFSA. Internally, the list
            will be sorted to simplify the minimization logic. Repeated items
            are inserted as many times as they are found.
        minimize : bool
            Whether to run the minimization or not. No minimization will
            return a full trie. Defaults to True.
        weight : bool
            Whether to collect edge weights after minimization. Defaults
            to `True`.
        join_trans : bool
            Whether to join single transitions after the final minimization.
            Defaults to `False`.
        delimiter : str
            If `join_trans` is set to `True`, informs the string to be
            used a transition symbol delimiter. Defaults to `" "` (single
            white space).
        """

        # get parameters
        minimize = kwargs.get("minimize", True)
        weight = kwargs.get("weight", True)
        join_trans = kwargs.get("join_trans", False)
        delimiter = kwargs.get("delimiter", " ")

        # Take a sorted set of the sequences and store its number
        sequences = sorted(sequences)
        self._num_sequences = len(sequences)

        # Make sure the words are sorted and add a dummy empty previous
        # word for the loop
        for previous_seq, seq in utils.pairwise([""] + sequences):
            self._insert_single_seq(seq, previous_seq, minimize)

        # Minimize the entire graph, no restrictions, so that we clean
        # `self._unchecked_nodes`.
        # See comments on the `minimize` flag in the `._minimize()` method.
        self._minimize(0, minimize)

        # Collect (or update) edge weights if requested. While this means
        # a second pass at all the sequences, it is better to do it in
        # separate step/method: it doesn't affect the computation speed
        # significantly, makes the logic easier to follow, and allows
        # to decide whether to collect the weights or not.
        if weight:
            self._collect_weights(sequences)

        # After the final minimization, we can join single transitions
        # if requested. In any case, we will make a copy of nodes and edges
        # in their current state, which can be used by other functions
        # and methods (mainly .lookup()) as well as by the user, if so
        # desired.
        self.lookup_nodes = copy.deepcopy(self.nodes)
        if join_trans:
            self._join_transitions(delimiter)

    def _insert_single_seq(self, seq, previous_seq, minimize):
        """
        Internal function for single sequence insertion.
        """

        # Obtain the length of the common_prefix between the current word
        # and the one added before it, then using ._unchecked_nodes for
        # removing redundant nodes, proceeding from the last one down to
        # the the common prefix size. The list will be truncated at that
        # point.
        # See comments on the `minimize` flag in the `._minimize()` method.
        prefix_len = utils.common_prefix_length(seq, previous_seq)
        self._minimize(prefix_len, minimize)

        # Add the suffix, starting from the correct node mid-way through the
        # graph, provided there are unchecked nodes (otherwise, just
        # start at the root). If there is no shared prefix, the node is
        # obviously the root (the only thing the two sequences share is
        # the start symbol)
        if not self._unchecked_nodes:
            node = self.nodes[0]
        else:
            node = self._unchecked_nodes[-1]["child"]

        # For everything after the common prefix, create as many necessary
        # new nodes and add them.
        for token in seq[prefix_len:]:
            # Create a new child node, build an edge to it, add it to the
            # list of unchecked nodes (there might be duplicates in the
            # future) and proceed until the end of the sequence
            child = DAFSANode(next(self._iditer))
            node.edges[token] = DAFSAEdge(child)
            self._unchecked_nodes.append(
                {"parent": node, "token": token, "child": child}
            )
            node = child

        # This last node from the above loop is a terminal one
        node.final = True

    def _minimize(self, index, minimize):
        """
        Internal method for graph minimization.

        Minimize the graph from the last unchecked item to `index`;
        final minimization, the default, traverses the entire data
        structure.

        The method allows the minimization to be overridden by setting to
        `False` the `minimize` flag (returning a trie). Due to the logic in
        place for the DAFSA minimization, this ends up executed as a
        non-efficient code, where all comparisons fails, but it is
        necessary to do it this watransitionsy to clean the list of unchecked nodes.
        This is not an implementation problem: this class is not supposed
        to be used for generating tries (there are more efficient ways of
        doing that), but it worth having the flag in place for experiments.
        """

        # Please note that this loop could be removed, but it would
        # unnecessarily complicate a logic which is already not immediately
        # intuitive (even if less idiomatic). Also note that, to guarantee
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
                unchecked_node = self._unchecked_nodes.pop()
                parent = unchecked_node["parent"]
                token = unchecked_node["token"]
                child = unchecked_node["child"]

                # If the child is already among the minimized nodes, replace it
                # with one previously encountered, also setting the sentinel;
                # otherwise, add the state to the list of minimized nodes.
                # The logic is to iterate over all self.nodes items,
                # compare each `node` with the `child` (using the internal
                # `.__eq__()` method), and carry the key/index in case
                # it is found.
                child_idx = [
                    node_idx
                    for node_idx, node in self.nodes.items()
                    if node == child and minimize
                ]

                if child_idx:
                    # Use the first node that matches, and make sure to
                    # carry the information about final state of the
                    # child, if that is the case
                    if parent.edges[token].node.final:
                        self.nodes[child_idx[0]].final = True
                    parent.edges[token].node = self.nodes[child_idx[0]]

                    # Mark the graph as changed, so we restart the loop
                    graph_changed = True
                else:
                    self.nodes[child.node_id] = child

            # Only leave the loop if the graph was untouched
            if not graph_changed:
                break

    def _join_transitions(self, delimiter):
        """
        Internal function for joining unique edges.

        The function joins paths of unique edges into single edges with
        compound transitions, removing redundant nodes. A redundant node
        is defined as one that (a) is not final, (b) emits a single transition,
        (b) receives a single transition, and (d) its source emits a single
        transition.

        Internally, the function will call the `._joining_round()`
        method until no more candidates for joining are available.
        Performing everything in a single step would require a more complex
        logic.

        Parameters
        ----------
        delimiter : str
            The string to be used as a transition delimiter.
        """

        # Perform joining operations until no more are possible
        while True:
            if self._joining_round(delimiter) == 0:
                break

    def _joining_round(self, delimiter):
        """
        Internal function for the unique-edge joining algorithm.

        This function will be called a successive number of times by
        `._join_transitions()`, until no more candidates for unique-edge
        joining are available (as informed by its return value).

        Parameters
        ----------
        delimiter : str
            The string to be used as a transition delimiter.

        Returns
        -------
        num_operations: int
            The number of joining operations that was performed. When zero,
            it signals that no more joining is possible.
        """

        # Build inverse map of which state receives from which other state,
        # along with a counter for `sources` and `targets` so that we
        # can exclude nodes receiving more that one edge and/or emitting
        # more than one edge
        edges = []
        for source_id, node in self.nodes.items():
            edges += [
                {"source": source_id, "target": node.edges[label].node.node_id}
                for label in node.edges
            ]
        sources = Counter([edge["source"] for edge in edges])
        targets = Counter([edge["target"] for edge in edges])

        # Select nodes that (a) receive a single transition, (b) are not
        # final, (c) their source has a single emission
        transitions = []
        transitions_nodes = []
        for node_id, node in self.nodes.items():
            if targets[node_id] > 1:
                continue
            if sources[node_id] > 1:
                continue
            if node.final:
                continue

            # Get the transition that leads to this node; `transition_to`
            # is easy because we know to be emitting only one edge
            edge_info = [edge for edge in edges if edge["target"] == node_id][0]
            label_from = [
                label
                for label in self.nodes[edge_info["source"]].edges
                if self.nodes[edge_info["source"]].edges[label].node.node_id
                == edge_info["target"]
            ][0]
            label_to = list(node.edges.keys())[0]

            # collect the transition as long as it does not involve
            # nodes already in the list
            if all([node_id not in transitions_nodes for node_id in edge_info]):
                transitions_nodes += edge_info
                transitions.append(
                    {
                        "edge": edge_info,
                        "label_from": label_from,
                        "label_to": label_to,
                    }
                )

        # Now that we have collected the transitions that we can
        # combine, combine them creating new transitions
        for transition in transitions:
            new_label = delimiter.join(
                [transition["label_from"], transition["label_to"]]
            )

            # change the transition
            self.nodes[transition["edge"]["source"]].edges[
                new_label
            ] = DAFSAEdge(
                self.nodes[transition["edge"]["target"]]
                .edges[transition["label_to"]]
                .node,
                self.nodes[transition["edge"]["target"]]
                .edges[transition["label_to"]]
                .weight,
            )
            self.nodes[transition["edge"]["source"]].edges.pop(
                transition["label_from"]
            )
            self.nodes.pop(transition["edge"]["target"])

        # return number of transitions performed
        return len(transitions)

    def _collect_weights(self, sequences):
        """
        Updates or collects weights for the sequences.

        This method requires the minimized graph to be already in place.
        As commented in `.insert()`, while it means a second pass at all
        sequences, it is better to have it as a separate method.
        """

        for seq in sequences:
            # Start at the root
            node = self.nodes[0]
            node.weight += 1

            # Follow the path, updating along the way
            for token in seq:
                node.edges[token].weight += 1
                node = node.edges[token].node
                node.weight += 1

    # TODO: support lookup after transition joining, deciding whether
    # to multiply or not
    # TODO: should sum weights?
    def lookup(self, seq):
        """
        Checks if a sequence is expressed by the graph.

        The function does not return all possible potential paths, nor
        the cumulative weight: if this is needed, the DAFSA object should
        be converted to a Graph and other libraries, such as `networkx`,
        should be used.

        Parameters
        ----------
        seq : sequence
            Sequence to be checked for presence/absence.

        Returns
        -------
        ret : DAFSANode or None
            Either a DAFSANode with a final state that can be reached
            following the specified sequence, or None if no path can
            be found.
        """

        # Start at the root
        node = self.lookup_nodes[0]

        # If we can follow a path, it is valid, otherwise return None
        for token in seq:
            if token not in node.edges:
                return None
            node = node.edges[token].node

        # Check if the last node is indeed a final one (so we don't
        # match prefixes alone)
        if not node.final:
            return None

        return node

    def count_nodes(self):
        """
        Returns the number of minimized nodes in the structure.
        """

        return len(self.nodes)

    def count_edges(self):
        """
        Returns the number of minimized edges in the structure.
        """

        return sum([len(node.edges) for node in self.nodes.values()])

    def count_sequences(self):
        """
        Returns the number of sequences the structure.
        """

        return self._num_sequences

    def __str__(self):
        """
        Returns a readable, multiline textual representation.
        """

        # Add basic statistics
        buf = [
            "DAFSA with %i nodes and %i edges (%i sequences)"
            % (self.count_nodes(), self.count_edges(), self.count_sequences())
        ]

        # Add information on nodes
        # Override pylint false positive
        # pylint: disable=no-member
        for node_id in sorted(self.nodes):
            node = self.nodes[node_id]
            buf += [
                "  +-- #%i: %s %s"
                % (
                    node_id,
                    repr(node),
                    [(attr, n.node.node_id) for attr, n in node.edges.items()],
                )
            ]

        # build a single string and returns
        return "\n".join(buf)

    def to_dot(self, **kwargs):
        """
        Returns a representation in the DOT (Graphviz) language.

        Parameters
        ----------
        label_nodes
        weight_scale
        """

        # collect the maximum node weight for later computing the size
        max_weight = max([node.weight for node in self.nodes.values()])

        # collect all nodes
        dot_nodes = []
        for node in self.nodes.values():
            # List for collecting node attributes
            node_attr = []

            # Decide on node label
            if kwargs.get("label_nodes", False):
                node_attr.append('label="%i"' % node.node_id)
            else:
                node_attr.append('label=""')

            # Decide on node shape
            if node.node_id == 0:
                node_attr.append('shape="doubleoctagon"')
            elif node.final:
                node_attr.append('shape="doublecircle"')
            else:
                node_attr.append('shape="circle"')

            # Set node size
            node_attr.append(
                "width=%.2f" % ((1.0 * (node.weight / max_weight)) ** 0.5)
            )

            # All nodes as filled
            node_attr.append('style="filled"')

            # Build the node attributes string
            buf = '"%i" %s ;' % (node.node_id, "[%s]" % ",".join(node_attr))
            dot_nodes.append(buf)

        # add other edges
        dot_edges = []
        for left in self.nodes.values():
            for attr, right in left.edges.items():
                buf = '"%i" -> "%i" [label="%s",penwidth=%i] ;' % (
                    left.node_id,
                    right.node.node_id,
                    attr,
                    right.weight * kwargs.get("weight_scale", 1.5),
                )
                dot_edges.append(buf)

        # load template and build .dot source
        template = utils.RESOURCE_DIR / "template.dot"
        with open(template.as_posix()) as handler:
            source = handler.read()

        source = source.replace("$dot_nodes$", "\n".join(dot_nodes))
        source = source.replace("$dot_edges$", "\n".join(dot_edges))

        return source

    # TODO: decide on node label as _to_graphviz?
    # TODO: how to express final?
    def graphviz_output(self, output_file, dpi=300):
        """
        Generates a visualization by calling the local `graphviz`.

        The filetype will be decided from the extension of the `filename`.

        Parameters
        ----------
        output_file : str
            The path to the output file.
        dpi : int
            The output resolution. Defaults to 300.
        """

        # Obtain the source and make it writable
        dot_source = self.to_dot()
        dot_source = dot_source.encode("utf-8")

        # Write with `subprocess`
        output.graphviz_output(dot_source, output_file, dpi)

    def to_graph(self):
        """
        Returns a `networkx` graph for the DAFSA.

        The user can use for everything a normal graph would be used,
        shortest path, etc...
        """

        graph = nx.Graph()

        for node_id, node in self.nodes.items():
            graph.add_node(node_id)
            graph.nodes[node_id]["final"] = node.final

            for left in self.nodes.values():
                for label, right in left.edges.items():
                    l_id = left.node_id
                    r_id = right.node.node_id
                    graph.add_edge(l_id, r_id, weight=right.weight)
                    graph[l_id][r_id]["label"] = label

        return graph
