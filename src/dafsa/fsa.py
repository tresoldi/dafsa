# Import Python standard libraries
import os
from types import GeneratorType
from typing import Optional, Tuple

# Import from local modules
from .common import validate_expression, gen_source
from .exceptions import InvalidWildCardExpressionError


class FSANode:
    """
    Class representing a Finite State Automaton (FSA) node.
    """

    __slots__ = "id", "val", "children", "terminal", "count"

    # TODO: move `val` to arbitrary hashable element
    def __init__(self, _id: int, val: str):
        """
        Initialize a Finite State Automaton(FSA) Node.

        :param _id: A unique numerical ID assigned to this node.
        :param val: The value associated with the node.
        """

        self.id = _id
        self.val = val
        self.children: dict = {}
        self.terminal: bool = False
        self.count: int = 0

    # TODO: move `element` to arbitrary hashable element
    # TODO: as _id is mandatory, should we invert arg order to mimic __init__?
    def add_child(self, element: str, _id: int):
        """
        Adds a child edge to the current node.

        :param element: The character label that the child node will have.
        :param _id: A unique numerical ID assigned to this node.
        """

        self.children[element] = FSANode(_id, element)

    # TODO: decide what to do if the element is missing
    # TODO: move `element` to arbitrary hashable element
    def __getitem__(self, element):
        """
        Returns the child node.

        :param element: The letter (or label) corresponding to the child node.
        :return: The child node.
        """

        return self.children[element]

    # TODO: follow as closely as possible the representation of version 1.0
    def __str__(self) -> str:
        """
        Returns a string representation of the current FSA node.

        :return: The string representation of the node.
        """

        strarr = [self.val, str(self.count)]

        if self.terminal:
            strarr.append("1")
        else:
            strarr.append("0")

        for element, node in self.children.items():
            strarr.append(element)
            strarr.append(str(node.id))

        return "".join(strarr)

    def __repr__(self) -> str:
        """
        Returns a nicely formatted textual representation of the current node.

        :return: A textual representation of the current node.
        """
        return "{0}(id={1}, label={2}, EOW={3}, count={4})".format(
            self.__class__.__name__, self.id, self.val, self.terminal, self.count
        )

    # TODO: decide whether to use `count` (using __repr__?)
    def __eq__(self, other) -> bool:
        """
        Checks if two FSA nodes are equal.

        Currently, nodes are considered equal if they have the same textual
        representation.

        :return: A boolean informing whether the two nodes are equal.
        """

        return self.__str__() == other.__str__()

    # TODO: we should really mode to __repr__, accounting for `count`
    def __hash__(self):
        """
        Return a hash for the current node.

        :return: The hash value for the current node.
        """

        return self.__str__().__hash__()


class FSA:
    """
    Class representing a Finite State Automaton (FSA) node.

    Both tries and dafsas inherit from this class. As many common methods as
    possible should be moved here.
    """

    __slots__ = "_id", "_num_seqs", "root"

    def __init__(self, root: FSANode):
        self._id = 1
        self._num_seqs = 1  # starts with the empty sequence
        self.root = root

    # TODO: move to arbitrary sequence type
    # TODO: cache seq len?
    def __contains__(self, seq: str) -> bool:
        """
        Checks if a sequence is expressed by the automaton, overloading `in`.

        :param seq: The sequence to be searched.
        :return: Whether the sequence is expressed by the automaton.
        """

        # The root is an empty string, and always present
        # TODO: update with arbitrary sequence typing
        if seq == "":
            return True
        if seq is None:
            return False

        node = self.root
        for idx, element in enumerate(seq):
            if element not in node.children:
                return False
            else:
                node = node[element]
                if node.terminal and idx == len(seq) - 1:
                    return True

        return False

    # TODO: move to arbitrary sequence type
    def __contains_prefix(self, prefix: str) -> Tuple[bool, Optional[FSANode]]:
        """
        Internal method for checking if a prefix is present in the automaton.

        :param prefix: The prefix sequence.
        :return: A tuple whose first element is a boolean, indicating whether the
            prefix is found, and whose second element is the node where the
            prefix ends. If the prefix is not found, the second element will be
            `None`.
        """

        if prefix == "":
            return True, self.root
        if prefix is None:
            return False, None

        node = self.root
        for element in prefix:
            if element in node.children:
                node = node[element]
            else:
                return False, None

        return True, node

    # TODO: move to arbitrary sequence type
    def contains_prefix(self, prefix: str) -> bool:
        """
        Checks whether a prefix is present in the automaton.

        :param prefix: The prefix sequence.
        :return: A boolean indicating whether the prefix is present.
        """

        contains, _ = self.__contains_prefix(prefix)
        return contains

    @staticmethod
    def __words_with_wildcard(node, wildcard, index, current_word="", with_count=False):
        """
        Description:
            Returns all the words where the wildcard pattern matches.
            This method uses backtracking to recursively traverse nodes in the DAWG for wildcard characters '?' and '*'
        Args:
            :arg node (lexpy._base.node.FSANode): Current Node in the Finite State Automaton
            :arg wildcard (str) : The wildcard pattern as input
            :arg index (int): The current index in the wildcard pattern
            :arg current_word (str): Word formed till now
        Returns:
            :returns words(list): Returns the list of words where the wildcard pattern matches.
        """
        if not node or not wildcard or index < 0:
            return []

        if node.terminal and index >= len(wildcard) and current_word:
            return [(current_word, node.count)] if with_count else [current_word]

        if index >= len(wildcard):
            return []

        words = []
        letter = wildcard[index]

        if letter == "?":
            for child in node.children:
                child_node = node[child]

                child_words = FSA.__words_with_wildcard(
                    child_node,
                    wildcard,
                    index + 1,
                    current_word + child,
                    with_count=with_count,
                )
                words.extend(child_words)

        elif letter == "*":
            words_at_current_level = FSA.__words_with_wildcard(
                node, wildcard, index + 1, current_word, with_count=with_count
            )
            words.extend(words_at_current_level)

            if node.children:
                for child in node.children:
                    child_node = node[child]
                    child_words = FSA.__words_with_wildcard(
                        child_node,
                        wildcard,
                        index,
                        current_word + child,
                        with_count=with_count,
                    )
                    words.extend(child_words)
            elif node.terminal and index == len(wildcard) - 1:
                return [(current_word, node.count)] if with_count else [current_word]

        else:
            if letter in node.children:
                child_node = node[letter]
                child_words = FSA.__words_with_wildcard(
                    child_node,
                    wildcard,
                    index + 1,
                    current_word + child_node.val,
                    with_count=with_count,
                )
                words.extend(child_words)

        return words

    def search(self, wildcard, with_count=False):
        """
        Description:
            Returns all the words where the wildcard pattern matches.
        Args:
            :arg wildcard(str) : The wildcard pattern as input
        Returns:
            :returns words(list): Returns the list of words where the wildcard pattern matches.
        """
        words = []
        if wildcard is None:
            raise ValueError("Search pattern cannot be None")

        if wildcard == "":
            return words
        try:
            wildcard = validate_expression(wildcard)
        except InvalidWildCardExpressionError:
            raise

        if wildcard.isalpha():
            present, node = self.__contains_prefix(wildcard)
            if present and node.terminal:
                words.append((wildcard, node.count)) if with_count else words.append(
                    wildcard
                )
                # words.append(wildcard)
            return words

        return FSA.__words_with_wildcard(
            self.root, wildcard, 0, self.root.val, with_count=with_count
        )

    def search_with_prefix(self, prefix, with_count=False):
        """
        Description:
            Returns a list of words which share the same prefix as passed in input. The words are by default sorted
            in the increasing order of length.
        Arguments:
            :arg (str) prefix: The Prefix string
        Returns:
            :returns (list) words: which share the same prefix as passed in input
        """
        if not prefix:
            return []
        _, node = self.__contains_prefix(prefix)
        if node is None:
            return []
        return FSA.__words_with_wildcard(node, "*", 0, prefix, with_count=with_count)

    def add_all(self, source):
        """
        Description:
            Add a collection of words from any of the following passed in input
                1. File (complete path to the file) or a `File` type
                2. Generator
                3. List
                4. Set
                5. Tuple
            Words which are not of type string are not inserted in the Trie
        Args:
            :arg source (list, set, tuple, Generator, File)
        Returns:
            None
        """
        if isinstance(source, (GeneratorType, str, list, tuple, set)):
            pass
        elif hasattr(source, "read"):
            pass
        else:
            raise ValueError("Source type {0} not supported ".format(type(source)))

        if isinstance(source, str) and not os.path.exists(source):
            raise IOError("File does not exists")

        if isinstance(source, str) or hasattr(source, "read"):
            source = gen_source(source)

        for word in source:
            if type(word) == str:
                self.add(word)

    def get_word_count(self):
        """
        Description:
            Returns the number of words in Trie Data structure
        Returns:
            :returns (int) Number of words
        """
        return max(0, self._num_seqs - 1)

    def search_within_distance(self, word, dist=0, with_count=False):
        row = list(range(len(word) + 1))
        words = []
        for child in self.root.children:
            self._search_within_distance(
                word,
                self.root.children[child],
                child,
                child,
                words,
                row,
                dist,
                with_count=with_count,
            )
        return words

    def _search_within_distance(
        self, word, node, letter, new_word, words, row, dist=0, with_count=False
    ):
        cols = len(word) + 1
        curr_row = [row[0] + 1]
        for col in range(1, cols):
            i = curr_row[col - 1] + 1
            d = row[col] + 1
            if word[col - 1] != letter:
                r = row[col - 1] + 1
            else:
                r = row[col - 1]
            curr_row.append(min(i, d, r))

        if curr_row[-1] <= dist and node.terminal:
            words.append((new_word, node.count)) if with_count else words.append(
                new_word
            )

        if min(curr_row) <= dist:
            for child_node in node.children:
                self._search_within_distance(
                    word,
                    node.children[child_node],
                    child_node,
                    new_word + child_node,
                    words,
                    curr_row,
                    dist,
                    with_count=with_count,
                )
