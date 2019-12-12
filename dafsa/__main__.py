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


def parse_arguments():
    """
    Parses arguments and returns a namespace.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--type",
        type=str,
        choices=["stdout", "dot", "png", "pdf", "svg", "gml"],
        default="stdout",
        help="Type of output (default: 'stdout')",
    )
    parser.add_argument(
        "-c",
        "--condense",
        action="store_true",
        help="Whether to condense the automaton, joining sequences of "
        "transitions into single compound transitions (default: false)",
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
    dafsa = DAFSA(seqs, condense=args.condense)

    # Generate output
    if args.type == "stdout":
        print(str(dafsa))
    elif args.type == "dot":
        with open(args.output, "w") as handler:
            handler.write(dafsa.to_dot())
    elif args.type in ["png", "pdf", "svg"]:
        dafsa.write_figure(args.output, args.dpi)
    elif args.type == "gml":
        dafsa.write_gml(args.output)


if __name__ == "__main__":
    main()
