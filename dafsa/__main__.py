#!/usr/bin/env python3
# encoding: utf-8

"""
__main__.py

Module for command-line execution and computation of DAFSAs.
"""

# Import Python standard libraries
import argparse

# Import our library
from dafsa import DAFSA

# TODO: option for minimization from command line


def parse_arguments():
    """
    Parses arguments and returns a namespace.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--type",
        type=str,
        choices=["stdout", "txt", "dot", "png"],
        default="stdout",
        help="Type of output (default: 'stdout')",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="The resolution output (default: 300)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Full path to the output file (if any).",
    )
    parser.add_argument(
        "source",
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
    with open(args.source) as handler:
        seqs = [line.strip() for line in handler]

    # Split data into tokens if there are spaces
    spaces = [" " in seq for seq in seqs]
    if any(spaces):
        seqs = [seq.split() for seq in seqs]

    # build object
    dafsa = DAFSA(seqs)

    # Generate output
    if args.type == "stdout":
        print(str(dafsa))
    elif args.type == "txt":
        with open(args.output, "w") as handler:
            handler.write(str(dafsa))
            handler.write("\n")
    elif args.type == "dot":
        with open(args.output, "w") as handler:
            handler.write(dafsa.to_dot())
    elif args.type in ["png"]:
        dafsa.graphviz_output(args.output, args.dpi)


if __name__ == "__main__":
    main()
