from .fsa import FSA, FSANode


class Trie(FSA):
    """
    Class representing a Trie.
    """

    __slots__ = "root"

    # TODO: confirm, but this is setting 0 as initial id
    def __init__(self):
        """
        This method initializes the Trie instance by creating the root node.

        By default, the id of the root node is 1 and its label is an empty string
        `""`. The number of sequences in a new trie is, at fist, 1 (only the
        empty sequence).
        """

        root = FSANode(0, "")
        super(Trie, self).__init__(root)

    # TODO: should we overload `+` as well, with an implied single count
    # TODO: move to sequence of hashable
    # TODO: cache `len(seq)` for speed?
    def add(self, seq, count: int = 1):
        """
        Adds a sequence to the data structure.

        :param seq: The sequence to be inserted in the data structure.
        :param count: The number of times to insert the sequence (defaults to 1).
        """

        assert seq is not None, "Input sequence cannot be None"

        node = self.root
        for i, element in enumerate(seq):
            if element not in node.children:
                self._id += 1
                node.add_child(element, _id=self._id)

            node = node[element]
            if i == len(seq) - 1:
                node.terminal = True
                node.count += count
                self._num_seqs += count

    def __len__(self) -> int:
        """
        Returns the number of nodes in the data structure.

        :return: The number of nodes in the data structure.
        """
        return self._id
