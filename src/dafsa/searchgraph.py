# Import Python standard libraries
from typing import Hashable, List, Optional, Sequence, Tuple
from itertools import chain

# TODO; add __slots__
# TODO: can we have `init` and `value` at the same time?
# TODO: should `value` default to None instead of empty string?
# TODO: is `value` used only by minimization?
class SearchGraph:
    """
    Class representing a graph used for locating specific keys from within a set.

    This data structure was first coded as a tree (i.e., a trie), but during
    minimization it can evolve into a network, and it is better to use this
    name not to have users expecting "normal" tries. It is mostly an auxiliary
    data structure for obtaining the minimized array or graph exported
    with `networkx`.

    As the code derives from AndrasKovacs' initial implementation, which
    recoded chalup's that was itself a version modifier from John
    Paul Adamovsky's original implementation in C, this code, as other
    parts of the library, "feels" more C than Python. In particular,
    the usage of nodes as equivalent to pointers, which is part of what
    makes the minimization process so fast, will feel strange or bad
    to most Pythonistas, along with practices not recommended such as
    a method's `self` parameter being reassigned. Keeping the original
    implementation is a conscious decision.
    """

    def __init__(
        self,
        init: Optional[Sequence[Sequence[Hashable]]] = None,
        value: Hashable = "",
        terminal: bool = False,
        group_end: bool = False,
    ):
        """
        Initialization method.

        :param init: A collection of sequence of hashable elements to be added to the search graph.
            Minimization is *not* performed by default.
        :param value: The value for the node.
        :param terminal: Whether the node is a terminal node in the sequence. Used by minimization,
            should not be passed directly by the user.
        :param group_end: Whether the node represents the end of a group in the minimized array. Used
            by minimization, should not be passed directly by the user.
        """

        # Initialize the list of children for the current node; please
        # note that during minimization this will be cast to tuples in
        # order to obtain an immutable, and thus hashable, element.
        self.children = []

        # Set internal variables; `stable_ref` is the hash value used for
        # minimization, which stores the original hash value before
        # manipulation (as modifying the node and/or its children would
        # lead to different hash values)
        self.value: Hashable = value
        self.terminal: bool = terminal
        self.group_end: bool = group_end
        self.stable_ref = None  # TODO: add typing

        # Adds a set of the initial sequences, as weight counting is
        # performed, if requested, at a different step
        if init:
            for seq in sorted(set(init)):
                self._add(seq)

    def collect_elements(self) -> List[Hashable]:
        """
        Build a list of all elements used in the node and its children.

        The returned list includes a copy of each element for each time it is
        observed (it is *not* a set).

        Note that this could be collected, in a faster way, within the `.add()` method,
        but for design decisions (also accounting for the mutability of the Graph and
        the possibility of obtaining the elements for a subset) it was decided to
        perform it by iteration, even though this computationally more expansive.

        :return: A list of the elements used in the graph.
        """

        # TODO: drop the expansive list/chain operations with `if`s?
        return list(
            chain.from_iterable(
                [self.value]
                + [children.collect_elements() for children in self.children]
            )
        )

    def _add(self, sequence: Sequence[Hashable]):
        """
        Internal method for adding a sequence to the graph.

        Sequences should be added in sorted order.

        :param sequence: The sequence to be added to the graph.
        """

        for element in sequence:
            # If `self.children` is empty (very first element) or if its element is different,
            # add a new SearchGraph
            if not self.children or self.children[-1].value != element:
                self.children.append(SearchGraph())

            # Set the reference of the current element to the last one added, and the `value`
            # as well. Note that this is very C-like programming, following the original implementation,
            # and in most cases would be frowned upon (not entirely without reason) by Python
            # purists -- nonetheless, it *is* the intended implementation
            self = self.children[-1]
            self.value = element

        # Once adding the sequence is over, the last item must be set as a terminal
        self.terminal = True

    def _internal_repr(self) -> Tuple:
        """
        Internal method returning a hashable and representable version of the node.

        This is method is used by `__str__` and `__hash__`, providing a common and single point
        of representation that can be used by both.
        """

        # TODO; can drop this check?
        if not self.children:
            offspring = None
        else:
            offspring = tuple([child._internal_repr() for child in self.children])

        return (self.value, self.terminal, self.group_end, offspring)

    def __iter__(self):
        """
        Iterator for graph.

        The iterator will first yield all the children in the order they are stored or, if
        the are not children, the node itself.
        """

        for node_x in self.children:
            for node_y in node_x:
                yield node_y

        yield self

    def __str__(self):
        return str(self._internal_repr())

    def __hash__(self):
        return hash(self._internal_repr())

    def __eq__(self, other):
        return self._internal_repr() == other._internal_repr()

    def __lt__(self, other):
        if len(self.children) < len(other.children):
            return True

        return self._internal_repr() < other._internal_repr()
