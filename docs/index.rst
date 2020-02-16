.. dafsa documentation master file, created by
   sphinx-quickstart on Fri Nov 29 16:34:44 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to dafsa's documentation!
=================================

.. image:: https://img.shields.io/pypi/v/dafsa.svg
   :alt: PyPI
   :target: https://pypi.org/project/dafsa

.. image:: https://travis-ci.org/tresoldi/dafsa.svg?branch=master
   :alt: Travis
   :target: https://travis-ci.org/tresoldi/dafsa

.. image:: https://codecov.io/gh/tresoldi/dafsa/branch/master/graph/badge.svg
   :alt: codecov
   :target: https://codecov.io/gh/tresoldi/dafsa

.. image:: https://api.codacy.com/project/badge/Grade/a2b47483ff684590b1208dbb4bbfc3ee
   :alt: Codacy
   :target: https://www.codacy.com/manual/tresoldi/dafsa?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=tresoldi/dafsa&amp;utm_campaign=Badge_Grade

.. image:: https://readthedocs.org/projects/dafsa/badge/?version=latest
   :alt: Documentation Status
   :target: https://dafsa.readthedocs.io/en/latest/?badge=latest

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.3668870.svg
   :alt: Zenodo
   :target: https://zenodo.org/badge/DOI/10.5281/zenodo.3668870.svg

``dafsa`` is a Python library for computing
`Deterministic Acyclic Finite State
Automata <https://en.wikipedia.org/wiki/Deterministic_acyclic_finite_state_automaton>`__
(also known as “directed acyclic word graphs”, or DAWG) for purposes of
data exploration and visualization. DAFSAs are data
structures derived from `tries <https://en.wikipedia.org/wiki/Trie>`__
that allow to represent a set of sequences (typically character strings
or *n*-grams) in the form of a directed acyclic graph with a single
source vertex (the ``start`` symbol shared by all sequences) and at least one
sink edge (``final`` symbols, each pointed to by one or more sequences), such
as in the following image.

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/reduced_phonemes.png
   :alt: Example of a DAFSA graph

   Example of a DAFSA graph from a selection of segmented Italian words
   transcribed in the International Phonetic Alphabet

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   readme
   quickstart
   Modules <source/modules.rst>

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
