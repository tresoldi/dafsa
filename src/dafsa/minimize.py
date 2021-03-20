from collections import defaultdict
from copy import copy
from .trie import SeqTrie


def merge_redundant_nodes(trie: SeqTrie):
    # This function is the core of the compression method, using single references ("hashes") to identify
    # common paths, as in the reference implementation. Note that the hashing function is not called at
    # each request, but its value is stored as a reference value in the object itself. This is done both
    # for speed (no need to recompute) and to the logic, inherited from the original C implementation,
    # where objects are mutable and are manipulated, meaning that subsequent calls to the same object
    # could find a different status leading, as expected, to a different "hash"
    node_dict = {}
    for node in trie:
        node.ref_id = hash(node)
        if node.ref_id not in node_dict:
            node_dict[node.ref_id] = node
            node.children = [
                node_dict[child_node.ref_id] for child_node in node.children
            ]

        node.children = tuple(sorted(node.children))

    # TODO: solve all those tuple casting -- not as easy as it may seem
    clist_dict = {node.children: node.children for node in node_dict.values()}
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
            -1 * sum(len(inverse_dict[n]) for n in _trie),
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


def build_compression_array(trie, compress_dict, elements):
    end_node = SeqTrie(terminal=False, value="", group_end=True)
    end_node.children = ()

    # Initialize array, with the first element being the end node
    array_length = 1 + sum(len(x[0]) for x in compress_dict.values())
    array = [None] * array_length
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
            # sort_array = [0] * 26
            sort_array = [0] * len(elements)
            for i, clist in enumerate(trie_list):
                for y in clist:
                    # sort_array[ord(y.value) - ord("A")] = (i, y)
                    sort_array[elements.index(y.value)] = (i, y)

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
