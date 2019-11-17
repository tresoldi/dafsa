#!/usr/bin/env python3
# encoding: utf-8

"""
test_dafsa
==========

Tests for the `dafsa` package.
"""

# Import Python libraries
import unittest

# Import the library itself
import dafsa
import dafsa.utils


class TestDAFSA(unittest.TestCase):
    # TODO: write assertions
    def test_hardcoded(self):
        """
        Performs a test from a hardcoded list of strings.
        """

        seqs = ["tap","taps","top","tops"]

        # build object
        dafsa_obj = dafsa.DAFSA(seqs)


    def test_full_test(self):
        """
        Perform a full test by loading strings from a file.
        """

        # Load strings from file
        filename = dafsa.utils.RESOURCE_DIR / "ciura.txt"
        with open(filename.as_posix()) as handler:
            strings = [line.strip() for line in handler]

        # build object
        dafsa_obj = dafsa.DAFSA(strings)

        # don't print
        text = str(dafsa_obj)

        # simple checks
        assert dafsa_obj.lookup("deny") is not None
        assert dafsa_obj.lookup("dafsa") is None
        assert dafsa_obj.lookup("dawg") is None
