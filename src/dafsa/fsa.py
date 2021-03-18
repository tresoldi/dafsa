import os
from types import GeneratorType

from .common import validate_expression, gen_source
from .exceptions import InvalidWildCardExpressionError


class FSANode:
    """
    Class for Finite State Automaton(FSA) Node. Both Trie and Directed Acyclic Word Graph (DAWG) node definitions
    inherit from this class.
    """

    __slots__ = "id", "val", "children", "eow", "count"

    def __init__(self, _id, val):
        """
        Description:
            Initialize a Finite State Automaton(FSA) Node.
        Args:
            :arg _id (int) Unique numerical ID assigned to this node.
            :arg val (str) The Letter from alphabet.
        """

        self.id = _id
        self.val = val
        self.children = {}
        self.eow = False
        self.count = 0

    def add_child(self, letter, _id=None):
        """
        Description:
            To add a child edge to the current Node.
        Args:
            :arg letter (str) The character label that the child node will have.
            :arg id (int) Unique numerical ID assigned to this node.
        """
        self.children[letter] = FSANode(_id, letter)

    def __getitem__(self, letter):
        """
        Description:
            Returns the child node. To use this method first check if the key is present in the dictionary of children
            edges or use default as None
        Args:
            :arg (str) The letter(or label) corresponding to the child node
        Returns:
            :return (FSANode) The child Node
        """
        return self.children[letter]

    def __str__(self):
        """
        Description:
            Outputs a string representation of the FSA node. This is invoked when str(`FSANode`) is called.
        :return:
        """
        strarr = [self.val, str(self.count)]

        if self.eow:
            strarr.append("1")
        else:
            strarr.append("0")

        for letter, node in self.children.items():
            strarr.append(letter)
            strarr.append(str(node.id))

        return "".join(strarr)

    def __eq__(self, other):
        """
        Description:
            Equal only if string representations are same.
        :param other:
        :return: bool
        """
        return self.__str__() == other.__str__()

    def __hash__(self):
        """
        Description:
            Call the __hash__() method on the string representation.
        :return:
        """
        return self.__str__().__hash__()

    def __repr__(self):
        """
        Description:
            Returns a nicely formatted string of the FSA node. This is invoked when `repr()` is called.
        :return:
        """
        return "{0}(id={1}, label={2}, EOW={3}, count={4})".format(
            self.__class__.__name__, self.id, self.val, self.eow, self.count
        )


class FSA:
    """
    Base Class which defines the common methods both for `Trie` and `DAWG`.
    """

    __slots__ = "_id", "_num_of_words", "root"

    def __init__(self, root):
        self._id = 1
        self._num_of_words = 1
        self.root = root

    def __contains__(self, word):
        """
        Description:
            To enable the use of 'in' keyword on dawg. Returns true if the word is present in dawg else false
        Args:
            :arg word (str) The word to be searched
        Returns:
            :returns contains (boolean) True or False
        """
        if word == "":
            return True  # The root is an empty string. So it is always present
        if word is None:
            return False
        node = self.root
        for i, letter in enumerate(word):
            if letter in node.children:
                node = node[letter]
                if node.eow and i == len(word) - 1:
                    return True
            else:
                return False
        return False

    def __contains_prefix(self, prefix):
        """
        Description:
            Checks whether the prefix is present in the DAWG. If yes, returns (True, node) where the prefix ends else
            returns (False, None)
        Arguments:
            :arg (str) prefix: The Prefix string
        Returns:
            :returns (tuple)(exists, node):  If yes, returns (True, node) where the prefix ends else
            returns (False, None)
        """
        if prefix == "":
            return True, self.root
        if prefix is None:
            return False, None
        node = self.root
        for i, letter in enumerate(prefix):
            if letter in node.children:
                node = node[letter]
            else:
                return False, None
        return True, node

    def contains_prefix(self, prefix):
        """
        Description:
            Returns a boolean indicating the presence of prefix in the DAWG data-structure
        Arguments:
            :arg (str) prefix: The Prefix string
        Returns:
            :returns (boolean) True, if present, else False.
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

        if node.eow and index >= len(wildcard) and current_word:
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
            elif node.eow and index == len(wildcard) - 1:
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
            if present and node.eow:
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
        return max(0, self._num_of_words - 1)

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

        if curr_row[-1] <= dist and node.eow:
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
