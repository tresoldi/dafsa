#!/usr/bin/env python

from copy import copy
from collections import defaultdict

FILENAME = "resources\dna.txt"


class SeqTrie(object):
    def __init__(self, init=None, terminal=False, value="", group_end=False):
        self.children = []
        self.terminal :bool= terminal
        self.value = value
        self.group_end :bool= group_end

        # TODO: do we still need this to be sorted?
        if init:
            for seq in sorted(init):
                self._add(seq)

    def _add(self, seq):
        for element in seq:
            # If `self.children` is empty (very first element) or if its element is different,
            # add a new SeqTrie
            if not self.children or self.children[-1].value != element:
                self.children.append(SeqTrie())

            # Set the reference of the current element to the last one added, and the `value`
            # as well. Note that this is very C-like programming, following the original implementation,
            # and in most cases would be frowned upon (not entirely without reason) by Python
            # purists -- nonetheless, it *is* the intended implementation
            self = self.children[-1]
            self.value = element

        # Once adding the sequence is over, the last item must be set as a terminal
        self.terminal = True

    def __iter__(self):
        for x in self.children:
            for y in x.__iter__():
                yield y
        yield self

    def build_ref(self):
        if len(self.children) > 0:
            offspring = ":".join([c.build_ref() for c in self.children])
        else:
            offspring = "NONE"

        return "[%s,%s,%s,%s]" % (
            self.value,
            str(self.terminal),
            str(self.group_end),
            offspring,
        )

    def __str__(self):
        return str(self.build_ref())

    def __hash__(self):
        return hash(self.build_ref())

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __lt__(self, other):
        if len(other.children) < len(self.children):
            return True

        return hash(self) < hash(other)


def extract_words(array, node_idx, carry=""):
    node = array[node_idx]
    if not node.value:
        return
    while True:
        for x in extract_words(array, node.children, carry + node.value):
            yield x
        if node.terminal:
            yield carry + node.value
        if node.group_end:
            break
        node_idx += 1
        node = array[node_idx]


def merge_redundant_nodes(trie):
    # Note that we cannot use an actual "hash", as the data structure is not preserved with the
    # modification, and subsequent calls will lead to different hash values; thus, we store
    # the "reference values", equivalent to hashes, in the internal `_ref` dictionary.
    _ref = {}

    node_dict = {}
    for node in trie:
        node.ref_str = node.build_ref()
        if node.ref_str not in node_dict:
            node_dict[node.ref_str] = node
            for idx, child_node in enumerate(node.children):
                node.children[idx] = node_dict[child_node.ref_str]

            node.children = sorted(node.children)

    # Cast all `node_dict` values to tuples, which are hashable
    # TODO: solve all those tuple casting
    clist_dict = {tuple(x.children): tuple(x.children) for x in node_dict.values()}
    for node in node_dict.values():
        node.children = clist_dict[tuple(node.children)]

    return clist_dict


def merge_child_list(clist_dict):
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
            -1 * sum(len(inverse_dict[node]) for node in _trie),
        ),
        reverse=True,
    )

    for clist in clist_sorted:
        for other in min((inverse_dict[t] for t in clist), key=len):
            if compress_dict[other] and set(clist) < set(compress_dict[other][-1]):
                compress_dict[other].append(clist)
                compress_dict[clist] = False
                break

    # Build the return dictionary with all tries and a boolean indicating whether to keep them
    return {_trie: keep for _trie, keep in compress_dict.items() if keep}


def build_compression_array(trie, compress_dict):
    end_node = SeqTrie(terminal=False, value="", group_end=True)
    end_node.children = ()

    # Initialize array, with the first element being the end node
    array_length = 1 + sum(len(x[0]) for x in compress_dict.values())
    array = [0] * array_length
    array[0] = end_node

    # Initialize the `clist_indices` dictionaries, with the empty tuple in first position (zero) and the first
    # position available (`pos`) as 1
    clist_indices = {(): 0}
    pos = 1

    for trie_list in compress_dict.values():
        # If there is a single element, it goes to position; otherwise, add all them
        if len(trie_list) == 1:
            clist_indices[trie_list[0]] = pos
        else:
            sort_array = [0] * 26
            for i, clist in enumerate(trie_list):
                for y in clist:
                    sort_array[ord(y.value) - ord("A")] = (i, y)

            trie_list.append([n for i, n in sorted(x for x in sort_array if x)])
            for clist in trie_list[:-1]:
                clist_indices[clist] = pos + len(trie_list[0]) - len(clist)

        # Update the array, also offsetting `pos` as much as necessary and setting `group_end`
        clist = trie_list[-1]
        array[pos : pos + len(clist)] = map(copy, clist)
        pos += len(clist)
        array[pos - 1].group_end = True

    for x in array:
        x.children = clist_indices[x.children]

    root = clist_indices[trie.children]
    root_node = SeqTrie(init=(), terminal=False, value="", group_end=True)
    root_node.children = root
    array.append(root_node)

    return array


######################## Read/check word list ###############################


def read_words(filename=FILENAME):
    wordlist = open(filename).read().split()
    wordlist = [word.strip() for word in wordlist]

    return wordlist


def main():
    # read data (already sorting)
    wordlist = sorted(read_words())
    if not all(all(c.isupper() for c in w) for w in wordlist):
        raise ValueError("Invalid wordlist")

    # build trie
    print("Building trie...")
    trie = SeqTrie(wordlist)

    # merge redundant nodes with hashes
    print("Merging redundant nodes...")
    clist_dict = merge_redundant_nodes(trie)

    # Merge child lists
    print("Merging child lists...")
    compress_dict = merge_child_list(clist_dict)

    # Create compressed trie structure
    print("Creating compressed node array...")
    array = build_compression_array(trie, compress_dict)
    root = array[-1].children

    ######################### check trie ###################################

    print("Checking output correctness...")
    if set(extract_words(array, root)) != set(wordlist):
        exit(1)

    print("Number of nodes:", len(array))

    print("Exporting as bit-packed array...")

    counter = -1
    for node in array:
        counter += 1
        print(counter, node.value, node.group_end, node.terminal, node.children)


if __name__ == "__main__":
    main()
