# __init__.py

# Version of the dafsa package
__version__ = "2.0"  # remember to sync with setup.py
__author__ = "Tiago Tresoldi"
__email__ = "tiago.tresoldi@lingfil.uu.se"

from .common import dummy, read_words, get_global_elements
from .minarray import extract_words
from .trie import SeqTrie
from .minimize import merge_redundant_nodes, merge_child_list, build_compression_array


def get_dafsa():
    from pathlib import Path

    filename = Path(__file__).parent.parent.parent / "resources" / "dna.txt"

    # read data (already sorting)
    # TODO: move sorting to trie
    # TODO: why tuple?
    wordlist = tuple(sorted(read_words(filename.as_posix())))

    # build trie
    print("Building trie...")
    trie = SeqTrie(wordlist)

    # merge redundant nodes with hashes
    print("Merging redundant nodes...")
    clist_dict = merge_redundant_nodes(trie)

    # Merge child lists
    print("Merging child lists...")
    compress_dict = merge_child_list(clist_dict)

    # Collect all elements so that we can use arbitrary ones and sort
    elements = get_global_elements(wordlist)

    # Create compressed trie structure
    print("Creating compressed node array...")
    array = build_compression_array(trie, compress_dict, elements)
    root = array[-1].children

    print("Checking output correctness...")
    if set(extract_words(array, root)) != set(wordlist):
        exit(1)

    print("Number of nodes:", len(array))

    counter = -1
    for node in array:
        counter += 1
        print(counter, node.value, node.group_end, node.terminal, node.children)

    return array
