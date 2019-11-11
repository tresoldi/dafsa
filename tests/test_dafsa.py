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


class TestDAFSA(unittest.TestCase):

    # First test with hardcoded list of words
    def test_hardcoded(self):
        seqs = [
            "defied",
            "defies",
            "defy",
            "defying",
            "deny",
            "denying",
            "tried",
            "tries",
            "try",
            "trying",
        ]

        # build object
        dafsa_obj = dafsa.DAFSA()
        dafsa_obj.insert(seqs)

        # don't print
        text = str(dafsa_obj)

        # simple checks
        assert dafsa_obj.lookup("deny") is not False
        assert dafsa_obj.lookup("dafsa") is False
        assert dafsa_obj.lookup("dawg") is False
