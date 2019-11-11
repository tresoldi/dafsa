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
import dafsa

def parse_arguments():
    """
    Parses arguments and returns a namespace.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--test",
        type=str,
        help="Temporary argument for development.")
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

if __name__ == "__main__":
    main()
