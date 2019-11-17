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

class TestNode(unittest.TestCase):
    def test_node(self):
        """
        Test node initialization.
        """

        # Missing ID
        with self.assertRaises(TypeError):
            node = dafsa.dafsa.DAFSANode()

        # Create nodes for testing
        node_a = dafsa.dafsa.DAFSANode(0)
        node_b = dafsa.dafsa.DAFSANode(1)
        node_c = dafsa.dafsa.DAFSANode(13)
        node_d = dafsa.dafsa.DAFSANode(14)
        node_b.final = True
        node_c.edges["x"] = dafsa.dafsa.DAFSAEdge(node_b, 2)
        node_d.edges["x"] = dafsa.dafsa.DAFSAEdge(node_b, 1)

        # __str__ and __repr__ assertions
        assert str(node_a) == ""
        assert str(node_b) == ""
        assert str(node_c) == "x|1"
        assert str(node_d) == "x|1"

        assert repr(node_a) == "0()"
        assert repr(node_b) == "F()"
        assert repr(node_c) == 'n(#1:<x>/2)'
        assert repr(node_d) == 'n(#1:<x>/1)'

        # __eq__ assertions
        assert node_a == node_b
        assert node_c == node_d
        assert node_a != node_c

        # __gt__ assertions
        assert node_a < node_c
        assert node_d > node_b

        # __hash__ assertions, follow _str__ for now
        assert hash(node_a) == hash(node_b)
        assert hash(node_c) == hash(node_d)
        assert hash(node_a) != hash(node_c)

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
