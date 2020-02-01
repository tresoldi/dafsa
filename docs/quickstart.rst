How to use
==========

The library offers a ``DAFSA`` object to compute automata, along with
methods for checking a sequence acceptance and for exporting the graph.
A minimal usage is shown here:

.. code:: python

   >>> from dafsa import DAFSA
   >>> d = DAFSA(["tap", "taps", "top", "tops", "dibs"])
   >>> print(d)
   DAFSA with 8 nodes and 9 edges (4 inserted sequences)
     +-- #0: 0(#1/4:<d>/1|#5/4:<t>/3) [('d', 1), ('t', 5)]
     +-- #1: n(#2/1:<i>/1) [('i', 2)]
     +-- #2: n(#3/1:<b>/1) [('b', 3)]
     +-- #3: F(#4/3:<s>/2) [('s', 4)]
     +-- #4: F() []
     +-- #5: n(#6/3:<a>/2|#9/3:<o>/1) [('a', 6), ('o', 9)]
     +-- #6: n(#3/2:<p>/2) [('p', 3)]
     +-- #9: n(#4/1:<p>/1) [('p', 4)]

Note how the resulting graph includes the 5 training sequences, with one
starting node (#0) that advances with either a ``t`` (observed four
times) or a ``d`` symbol (observed a single time), a subsequent node to
``t`` that only advances with ``a`` and ``o`` symbols (#1), and so on.

The structure is much clearer with a graphical representation:

.. code:: python

   >>> d.write_figure("example.png")

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/example.png
   :alt: First example

A DAFSA object allows to check for the presence or absence of a sequence
in its structure, returning a terminal node if it can find a path. If the
structure was computed using frequency weights, as by default, the
cumulative path weight is also returned.

.. code:: python

   >>> d.lookup("tap")
   (F(#4/5:<s>/3), 10)
   >>> d.lookup("tops")
   (F(), 13)
   >>> d.lookup("tapap") is None
   True
   >>> d.lookup("ta") is None
   True

Besides a number of alternatives for exporting visualizations, the structures
can also be exported as ``networkx`` graphs:

.. code:: python

   >>> d.to_graph()
   <networkx.classes.graph.Graph object at 0x7f51d15b7ac8>

The library includes a command-line tool for reading files with lists of
sequences, with one sequence per line:

::

   $ cat resources/dna.txt
   CGCGAAA
   CGCGATA
   CGGAAA
   CGGATA
   GGATA
   AATA

   $ dafsa resources/dna.txt -t png -o dna.png

Which will produce the following graph:

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/dna.png
   :alt: DNA example

Sequences are by default processed one character at time, with each
character assumed to be a single token. Pre-tokenized data can be
provided to the library in the format of a Python list or tuple, or
specified in source by using spaces as token delimiters:

.. code:: bash

   $ cat resources/phonemes.txt
   o kː j o
   o r e kː j o
   n a z o
   s e n t i r e
   s e n s o
   ɡ u a r d a r e
   a m a r e
   v o l a r e

   $ dafsa resources/phonemes.txt -t png -o phonemes.png

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/phonemes.png
   :alt: Phoneme example

DAFSA structures can be exported in PDF, SVG, GLM, and DOT formats.

Walkthrough example
-------------------

The most basic DAFSA is one expressing a single string, which links
the sequence of characters. As such, let's start by creating a DAFSA for
the string ``tap``, exploring the results.

.. code:: python

   >>> from dafsa import DAFSA
   >>> d1 = DAFSA(["tap"])
   >>> print(d1)
   DAFSA with 4 nodes and 3 edges (1 inserted sequences)
     +-- #0: 0(#1/1:<t>/1) [('t', 1)]
     +-- #1: n(#2/1:<a>/1) [('a', 2)]
     +-- #2: n(#3/1:<p>/1) [('p', 3)]
     +-- #3: F() []

When printing the structure, we are informed that it contains four nodes:
the three chracters ``t``, ``a``, and ``p`` from our string, plus a shared
final node. In order, skipping over information we will see later, we have:

The textual presentation given by ``print()`` lists all nodes, showing, in
order, the node index (in format ``#i:``, where `i` is the index), an
unambiguous textual representation (such as `#1/1:<t>/1`) and a list of
edges involved, conceived as a more human-friendly way of rendering the
information in the textual representation. In this example, we find out
that:

- A node of index 0 (``#0``) and type ``0`` (that is, a start symbol),
  which, as expressed by the list ``[('t', 1)]`` can only transition
  ("advance") with the character `t` moving to the node of index 1.
- A node of index 1 and type ``n`` (that is, a "normal" node which is neither
  a start or end symbol), which can only transition with the character
  `a` towards the node of index 2.
- A similar node, of index 2 and type ``n`` as above, which can only
  transition with the character `p` towards node 3.
- A node of index 3 and type ``F`` (that is, a final symbol), which by
  definition terminates a sequence.

A graphical representation, even if not impressive, can be created for
this DAFSA as well:

.. code:: python

   >>> d1.write_figure("d1.png")

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/d1.png
   :alt: Walkthrough first DAFSA

We can experiment with expanding the set of sequences covered by the DAFSA.
If we add a second string ``dibs``, thus with no overlap with the first
string, we can see that they will only share the starting and end symbols:

.. code:: python

   >>> d2 = DAFSA(["tap", "dibs"])
   >>> print(d2)
   DAFSA with 7 nodes and 7 edges (2 inserted sequences)
     +-- #0: 0(#1/2:<d>/1|#5/2:<t>/1) [('d', 1), ('t', 5)]
     +-- #1: n(#2/1:<i>/1) [('i', 2)]
     +-- #2: n(#3/1:<b>/1) [('b', 3)]
     +-- #3: n(#4/1:<s>/1) [('s', 4)]
     +-- #4: F() []
     +-- #5: n(#6/1:<a>/1) [('a', 6)]
     +-- #6: n(#4/1:<p>/1) [('p', 4)]

From the textual representation, we can see that the starting symbol (node
of index zero) has two transition alternatives: either the character `d`,
which will move towards node #1, or the character `t`, which will move to
node #5. As no information is shared between the two strings, each
initial transition will lead to independent and mandatory paths (from `d` to
`i`, `b`, and `s`, and from `t` to `a` and `p`), only overlapping in
terms of the final symbol at index #4: in fact, both node #3 and node
#6 can only advance towards this final node (as evidenced by the index
4 in the only entry in their transition lists).

The same information is expressed visually:

.. code:: python

   >>> d2.write_figure("d2.png")

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/d2.png
   :alt: Walkthrough second DAFSA

The usefulness of DAFSAs starts to become clear if we extend this set of
strings with new elements that show overlapping. For example, including
the string ``taps``, which overlaps with ``tap`` at the beginning and with
``dibs`` at the end, not only the pruning is triggered, detecting the
overlapping regions, but we also have counts for the most frequent
transitions:

.. code:: python

   >>> d3 = DAFSA(["tap", "dibs", "taps"])
   >>> print(d3)
   DAFSA with 7 nodes and 7 edges (3 inserted sequences)
     +-- #0: 0(#1/3:<d>/1|#5/3:<t>/2) [('d', 1), ('t', 5)]
     +-- #1: n(#2/1:<i>/1) [('i', 2)]
     +-- #2: n(#3/1:<b>/1) [('b', 3)]
     +-- #3: F(#4/3:<s>/2) [('s', 4)]
     +-- #4: F() []
     +-- #5: n(#6/2:<a>/2) [('a', 6)]
     +-- #6: n(#3/2:<p>/2) [('p', 3)]

In comparison with the second DAFSA, we notice that the string did not
introduce much more complexity, essentially compressing the data: the
node reached by the ``p`` character transition, shared by ``tap`` and
``taps``, allows a transition to the same node of index #3 that will
lead to a final ``-s`` as in ``dibs``. Along with the frequency information,
which is reported in the textual representation to the right of the
slashes (such as in the node of index 0, where ``t`` is twice as frequent
as ``d``, as the former accounts for the initial character of two of the
three strings), this can be visualized graphically:

.. code:: python

   >>> d3.write_figure("d3.png")

.. figure:: https://raw.githubusercontent.com/tresoldi/dafsa/master/figures/d2.png
   :alt: Walkthrough second DAFSA


From now, you can follow the other examples in this documentation and
start experimenting on your own. The ``dafsa``` library is distributed
with an homonymous command-line tool that reads plain text files and
allows to experiment directly.
