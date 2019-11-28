#!/usr/bin/env python3
# encoding: utf-8

"""
test_dafsa
==========

Tests for the `dafsa` package.
"""

# Import Python libraries
import sys
import tempfile
import unittest

# Import the library itself
import dafsa
import dafsa.utils


class TestNode(unittest.TestCase):
    def test_node(self):
        """
        Test nodes.
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
        if not str(node_a) == "":
            raise AssertionError()
        if not str(node_b) == "":
            raise AssertionError()
        if not str(node_c) == "x|1":
            raise AssertionError()
        if not str(node_d) == "x|1":
            raise AssertionError()

        if not repr(node_a) == "0()":
            raise AssertionError
        if not repr(node_b) == "F()":
            raise AssertionError
        if not repr(node_c) == "n(#1:<x>/2)":
            raise AssertionError
        if not repr(node_d) == "n(#1:<x>/1)":
            raise AssertionError

        # __eq__ assertions
        if not node_a == node_b:
            raise AssertionError
        if not node_c == node_d:
            raise AssertionError
        if not node_a != node_c:
            raise AssertionError

        # __gt__ assertions
        if not node_a < node_c:
            raise AssertionError
        if not node_d > node_b:
            raise AssertionError

        # __hash__ assertions, follow _str__ for now
        if not hash(node_a) == hash(node_b):
            raise AssertionError
        if not hash(node_c) == hash(node_d):
            raise AssertionError
        if not hash(node_a) != hash(node_c):
            raise AssertionError


class TestEdge(unittest.TestCase):
    def test_edge(self):
        """
        Test edges.
        """

        # Missing node
        with self.assertRaises(TypeError):
            edge_a = dafsa.dafsa.DAFSAEdge()

        # Create nodes for testing
        node_a = dafsa.dafsa.DAFSANode(15)
        node_a.final = True
        node_b = dafsa.dafsa.DAFSANode(16)

        # Create edges
        edge_a = dafsa.dafsa.DAFSAEdge(node_a)
        edge_b = dafsa.dafsa.DAFSAEdge(node_a, 2)
        edge_c = dafsa.dafsa.DAFSAEdge(node_b)

        # __str__ assertions
        if not str(edge_a) == "{node_id: 15, weight: 0}":
            raise AssertionError
        if not str(edge_b) == "{node_id: 15, weight: 2}":
            raise AssertionError
        if not str(edge_c) == "{node_id: 16, weight: 0}":
            raise AssertionError


class TestDAFSA(unittest.TestCase):
    def test_hardcoded(self):
        """
        Performs tests from hardcoded lists of strings.
        """

        seqs = ["tap", "taps", "top", "tops", "dib", "dibs", "tapping", "dibbing"]

        # build object, without and with joining
        # TODO: write tests?
        dafsa_obj_a = dafsa.DAFSA(seqs)
        dafda_obj_b = dafsa.DAFSA(seqs, join_trans=True)

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
        if not dafsa_obj.lookup("den") is None:
            raise AssertionError
        if not dafsa_obj.lookup("deny") is not None:
            raise AssertionError
        if not dafsa_obj.lookup("dafsa") is None:
            raise AssertionError
        if not dafsa_obj.lookup("dawg") is None:
            raise AssertionError

    def test_to_graphviz(self):
        """
        Tests DOT generation and Graphviz output.
        """

        # Load strings from file
        filename = dafsa.utils.RESOURCE_DIR / "ciura.txt"
        with open(filename.as_posix()) as handler:
            strings = [line.strip() for line in handler]

        # build object
        dafsa_obj = dafsa.DAFSA(strings)

        # Get a temporary filename (on Unix, it can be reused)
        handler = tempfile.NamedTemporaryFile()
        output_filename = "%s.png" % handler.name
        handler.close()

        # Test
        dafsa_obj.graphviz_output(output_filename)


if __name__ == "__main__":
    sys.exit(unittest.main())
