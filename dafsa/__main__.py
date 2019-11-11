#!/usr/bin/env python3
# encoding: utf-8

"""
__main__.py

Module for command-line execution and computation of DAFSAs.
"""

# Import Python standard libraries
import argparse
import configparser

# Import our library
from dafsa import DAFSA


def parse_arguments():
    """
    Parses arguments and returns a namespace.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t", "--test", type=str, help="Temporary argument for development."
    )
    args = parser.parse_args()

    return args


def main():
    """
    Main function for DAFSA computation from the command line.
    """

    # parse command line arguments
    args = parse_arguments()

    # Temporary results
    print(args)
    print("== ok ==")

    words = [
        "defy",
        "try",
        "defying",
        "deny",
        "denying",
        "tried",
        "defies",
        "tries",
        "defied",
        "dafsa",
        "trying",
    ]

    dafsa = DAFSA()
    dafsa.insert(words)

    print(
        "Read %d words into %d nodes and %d edges"
        % (len(words), dafsa.num_nodes(), dafsa.num_edges())
    )

    print(
        "r",
        [dafsa.root.node_id],
        [(label, str(n.node_id)) for label, n in dafsa.root.edges.items()],
    )
    for node in dafsa.nodes:
        print(
            node,
            [node.node_id, node.final],
            [(label, str(n.node_id)) for label, n in node.edges.items()],
        )

    print("deny", dafsa.lookup("deny"))
    print("dafsa", dafsa.lookup("dafsa"))
    print("dawg", dafsa.lookup("dawg"))


if __name__ == "__main__":
    main()
