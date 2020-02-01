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
        if not repr(node_c) == "n(#1/0:<x>/2)":
            raise AssertionError
        if not repr(node_d) == "n(#1/0:<x>/1)":
            raise AssertionError

        # __eq__ assertions
        if node_a == node_b:
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

        # repr_hash
        assert node_a.repr_hash() != node_b.repr_hash()


class TestEdge(unittest.TestCase):
    def test_edge(self):
        """
        Test edges.
        """

        # Missing node
        with self.assertRaises(TypeError):
            edge_a = dafsa.dafsa.DAFSAEdge()

        # Wrong type
        with self.assertRaises(TypeError):
            edge_a = dafsa.dafsa.DAFSAEdge(1)

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

        # __repr__ assertions
        assert repr(edge_a) == "{node: <F()>, weight: 0}"
        assert repr(edge_b) == "{node: <F()>, weight: 2}"
        assert repr(edge_c) == "{node: <n()>, weight: 0}"

        # hashes
        assert hash(edge_a) != edge_a.repr_hash()
        assert hash(edge_b) != edge_b.repr_hash()
        assert hash(edge_c) != edge_c.repr_hash()


class TestDAFSA(unittest.TestCase):
    def test_hardcoded(self):
        """
        Performs tests from hardcoded lists of strings.
        """

        seqs = [
            "tap",
            "taps",
            "top",
            "tops",
            "dib",
            "dibs",
            "tapping",
            "dibbing",
        ]

        # build object, without and with joining
        dafsa_obj_a = dafsa.DAFSA(seqs)
        dafsa_obj_b = dafsa.DAFSA(seqs, condense=True)

    def test_full_test(self):
        """
        Perform a full test by loading strings from a file.
        """

        # Load strings from file
        filename = dafsa.utils.RESOURCE_DIR / "ciura.txt"
        with open(filename.as_posix()) as handler:
            strings = [line.strip() for line in handler]

        # build object
        dafsa_obj_a = dafsa.DAFSA(strings)
        dafsa_obj_b = dafsa.DAFSA(strings, join_trans=True)

        # don't print
        text = str(dafsa_obj_a)
        text = str(dafsa_obj_b)

        # simple checks
        assert dafsa_obj_a.lookup("den") is None
        assert dafsa_obj_b.lookup("den") is None

        assert dafsa_obj_a.lookup("deny") is not None
        assert dafsa_obj_b.lookup("deny") is not None

        assert dafsa_obj_a.lookup("dafsa") is None
        assert dafsa_obj_b.lookup("dafsa") is None

    def test_to_figure(self):
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
        dafsa_obj.write_figure(output_filename)

    def test_to_graph(self):
        """
        Test `networkx` graph export.
        """

        # Load strings from file
        filename = dafsa.utils.RESOURCE_DIR / "ciura.txt"
        with open(filename.as_posix()) as handler:
            strings = [line.strip() for line in handler]

        # build object
        dafsa_obj = dafsa.DAFSA(strings)

        # Run function
        # TODO: assert results
        dafsa_obj.to_graph()

    def test_to_gml(self):
        """
        Test GML export.
        """

        # Load strings from file
        filename = dafsa.utils.RESOURCE_DIR / "ciura.txt"
        with open(filename.as_posix()) as handler:
            strings = [line.strip() for line in handler]

        # build object
        dafsa_obj = dafsa.DAFSA(strings)

        # Run function
        # TODO: assert results
        # Get a temporary filename (on Unix, it can be reused)
        handler = tempfile.NamedTemporaryFile()
        output_filename = "%s.png" % handler.name
        handler.close()

        dafsa_obj.write_gml(output_filename)


if __name__ == "__main__":
    # Explicitly creating and running a test suite allows to profile
    suite = unittest.TestLoader().loadTestsFromTestCase(TestNode)
    unittest.TextTestRunner(verbosity=2).run(suite)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestEdge)
    unittest.TextTestRunner(verbosity=2).run(suite)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestDAFSA)
    unittest.TextTestRunner(verbosity=2).run(suite)
