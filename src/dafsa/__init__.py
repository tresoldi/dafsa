# __init__.py

# Version of the dafsa package
__version__ = "2.0"  # remember to sync with setup.py
__author__ = "Tiago Tresoldi"
__email__ = "tiago.tresoldi@lingfil.uu.se"

from .common import read_words, extract_sequences, graphviz_output
from .searchgraph import SearchGraph
from .minimize import merge_redundant_nodes, merge_child_list, build_compression_array
from .minimize import minimize_trie


def get_dafsa(filename):
    # read data (already sorting)
    # TODO: move sorting to trie
    # TODO: why tuple?
    wordlist = tuple(sorted(read_words(filename.as_posix())))

    # build trie
    trie = SearchGraph(wordlist)

    array = minimize_trie(trie)

    # TODO: have flag
    # TODO: move extract_sequences() to DafsaArray
    if 1 == 2:
        if set(extract_sequences(array)) != set(wordlist):
            exit(1)

    # array.show()

    import matplotlib.pyplot as plt
    import networkx as nx

    G = array.to_graph()
    edge_labels = nx.get_edge_attributes(G, "label")
    formatted_edge_labels = {
        (elem[0], elem[1]): edge_labels[elem] for elem in edge_labels
    }

#    pos = nx.spring_layout(G)
#    nx.draw_networkx(G, arrows=True, with_labels=True, node_color="skyblue", pos=pos)
#    nx.draw_networkx_edge_labels(
#        G, pos, edge_labels=formatted_edge_labels, font_color="red"
#    )
#    plt.show()

    dot = array.to_dot()
#    graphviz_output(dot, "temp.png")

    return array
