# __init__.py

# Version of the dafsa package
__version__ = "2.0"  # remember to sync with setup.py
__author__ = "Tiago Tresoldi"
__email__ = "tiago.tresoldi@lingfil.uu.se"

from .common import read_words, get_global_elements, extract_words
from .trie import SeqTrie
from .minimize import merge_redundant_nodes, merge_child_list, build_compression_array
from .minimize import minimize_trie


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

    # TODO: remove wordlist argument
    array = minimize_trie(trie, wordlist)
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
