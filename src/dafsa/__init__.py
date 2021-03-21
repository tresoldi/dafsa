# __init__.py

# Version of the dafsa package
__version__ = "2.0"  # remember to sync with setup.py
__author__ = "Tiago Tresoldi"
__email__ = "tiago.tresoldi@lingfil.uu.se"

from .common import read_words, extract_sequences
from .searchgraph import SearchGraph
from .minimize import merge_redundant_nodes, merge_child_list, build_compression_array
from .minimize import minimize_trie


def get_dafsa(filename):
    # read data (already sorting)
    # TODO: move sorting to trie
    # TODO: why tuple?
    wordlist = tuple(sorted(read_words(filename.as_posix())))

    # build trie
    print("Building trie...")
    trie = SearchGraph(wordlist)

    # TODO: remove wordlist argument
    array = minimize_trie(trie)

    print("Checking output correctness...")
    if set(extract_sequences(array)) != set(wordlist):
        exit(1)

    print("Number of nodes:", len(array))

    counter = -1
    for node in array:
        counter += 1
        print(counter, node.value, node.group_end, node.terminal, node.child)

    return array
