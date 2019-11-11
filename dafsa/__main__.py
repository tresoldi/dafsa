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
        "filename",
        type=str,
        help="Filename with strings to be processed (one per line).",
    )
    args = parser.parse_args()

    return args


def main():
    """
    Main function for DAFSA computation from the command line.
    """

    # parse command line arguments
    args = parse_arguments()

    # load data
    with open(args.filename) as handler:
        seqs = [line.strip() for line in handler]

    # build object
    dafsa = DAFSA()
    dafsa.insert(seqs)

    print(str(dafsa))

    print()
    for needle in ["deny", "dafsa", "dawg"]:
        print("`%s` in dafsa:" % needle, dafsa.lookup(needle))


if __name__ == "__main__":
    main()
