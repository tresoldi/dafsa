"""Semirings: the algebra that makes a weight mean something.

A weighted automaton needs two operations. One combines weights **along** a path,
one combines weights **across** alternative paths, and together they have to be
associative and distributive so that the total is independent of the order the
paths happen to be visited in. That structure is a semiring, and its absence is
the deepest defect in 1.0: weights there were counters incremented while
re-walking sequences over an already-minimized graph, so an edge counter held the
total frequency of every sequence crossing that edge and a "cumulative weight"
was a sum of those. ``DAFSA(["dib", "tip", "tips", "top"]).lookup("tip")``
returned ``7`` for a sequence inserted once, which answers no question a caller
asked.

A semiring is a set with two operations satisfying:

* ``plus`` is associative and commutative, with identity :attr:`~Semiring.zero`.
* ``times`` is associative, with identity :attr:`~Semiring.one`.
* ``times`` distributes over ``plus`` from both sides.
* :attr:`~Semiring.zero` annihilates: ``times(zero, x) == zero``.

Every law above is checked against every built-in by the test suite, so a new
semiring added here is not trusted on inspection.

Notes
-----
There is deliberately no ``star`` (closure) operation. Every structure in this
library is acyclic, so no algorithm needs to sum over an unbounded number of
traversals of a cycle. Adding cyclic support later means adding ``star`` as an
optional protocol member, not revisiting these definitions.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Hashable

#: The weight type of a semiring. Deliberately unbounded: weights need not be
#: hashable, which is exactly why :meth:`Semiring.key` exists.
W = TypeVar("W")


class Semiring(Protocol[W]):
    """The interface every semiring satisfies.

    This is a :class:`~typing.Protocol`, so any object with these members works —
    a caller's own semiring needs no inheritance and no registration. The
    built-ins below are annotated as ``Semiring[...]`` at the point they are
    created, which makes conformance a type error rather than a runtime surprise.

    Attributes
    ----------
    zero
        Additive identity and multiplicative annihilator. Conventionally the
        weight of a path that does not exist.
    one
        Multiplicative identity. The weight of the empty path.
    idempotent
        Whether ``plus(a, a) == a``. True for the min/max-based semirings, which
        lets algorithms discard all but the best of several paths.
    commutative
        Whether ``times`` commutes. ``plus`` is required to commute by the
        semiring axioms, so this refers to ``times`` alone; it is false for
        things like a string-concatenation semiring.
    divisible
        Whether :meth:`divide` is defined, which is what weight pushing needs.
    """

    zero: W
    one: W
    idempotent: bool
    commutative: bool
    divisible: bool

    def plus(self, left: W, right: W) -> W:
        """Combine weights of alternative paths."""
        ...

    def times(self, left: W, right: W) -> W:
        """Combine weights along a single path."""
        ...

    def key(self, weight: W) -> Hashable:
        """Return a hashable canonical form of ``weight``.

        Used as part of a state's signature during minimization. It exists so
        that a semiring whose weights are unhashable, or which represents one
        value in several ways, can still be minimized.
        """
        ...

    def divide(self, left: W, right: W) -> W:
        """Return the ``w`` with ``times(w, right) == left``.

        Raises
        ------
        NotImplementedError
            If :attr:`divisible` is false.
        """
        ...


class _SemiringBase(Generic[W]):
    """Shared defaults for the built-in semirings.

    Not part of the public contract: :class:`Semiring` is a protocol, so nothing
    needs to inherit from anything. This exists only to avoid repeating the
    conservative defaults and the ``divide`` refusal six times.
    """

    __slots__ = ()

    idempotent: bool = False
    commutative: bool = True
    divisible: bool = False

    def divide(self, left: W, right: W) -> W:
        """Refuse division, which most semirings do not support.

        Parameters
        ----------
        left, right
            Ignored.

        Raises
        ------
        NotImplementedError
            Always. Check :attr:`~Semiring.divisible` first.
        """
        message = f"{type(self).__name__} is not divisible"
        raise NotImplementedError(message)

    def __repr__(self) -> str:
        """Return the semiring's class name."""
        return type(self).__name__


class BooleanSemiring(_SemiringBase[bool]):
    """``(or, and, False, True)`` — plain, unweighted acceptance.

    The default. A path's weight is whether it exists, so a "weighted" automaton
    over this semiring is just an acceptor and costs nothing extra.
    """

    __slots__ = ()

    zero: bool = False
    one: bool = True
    idempotent: bool = True

    def plus(self, left: bool, right: bool) -> bool:
        """Return the disjunction of two weights."""
        return left or right

    def times(self, left: bool, right: bool) -> bool:
        """Return the conjunction of two weights."""
        return left and right

    def key(self, weight: bool) -> Hashable:
        """Return ``weight``, which is already canonical and hashable."""
        return weight


class CountingSemiring(_SemiringBase[int]):
    """``(+, *, 0, 1)`` over integers — exact frequencies.

    This is what 1.0 was reaching for. Because arithmetic is exact, a count here
    is a count: the weight of a sequence is the number of times it was inserted,
    not a sum over everything sharing its edges.

    Not divisible: integer division is not exact, and a semiring that silently
    truncated would break weight pushing in a way that is hard to notice.
    """

    __slots__ = ()

    zero: int = 0
    one: int = 1

    def plus(self, left: int, right: int) -> int:
        """Return the sum of two weights."""
        return left + right

    def times(self, left: int, right: int) -> int:
        """Return the product of two weights."""
        return left * right

    def key(self, weight: int) -> Hashable:
        """Return ``weight``, which is already canonical and hashable."""
        return weight


class TropicalSemiring(_SemiringBase[float]):
    """``(min, +, inf, 0.0)`` — costs, and shortest paths.

    Weights add along a path and the best alternative wins, which is what makes
    ``min``-plus the natural home for edit distances, penalties, and any
    "cheapest analysis" question.
    """

    __slots__ = ()

    zero: float = math.inf
    one: float = 0.0
    idempotent: bool = True
    divisible: bool = True

    def plus(self, left: float, right: float) -> float:
        """Return the cheaper of two weights."""
        return left if left < right else right

    def times(self, left: float, right: float) -> float:
        """Return the combined cost along a path."""
        return left + right

    def key(self, weight: float) -> Hashable:
        """Return ``weight``, which is already canonical and hashable."""
        return weight

    def divide(self, left: float, right: float) -> float:
        """Return ``left - right``, the inverse of :meth:`times`.

        Raises
        ------
        ZeroDivisionError
            If ``right`` is :attr:`zero`. No weight ``w`` satisfies
            ``times(w, inf) == left`` for finite ``left``, so there is nothing
            honest to return.
        """
        if right == math.inf:
            message = "cannot divide by the tropical semiring's zero (inf)"
            raise ZeroDivisionError(message)

        return left - right


class LogSemiring(_SemiringBase[float]):
    """``(-log(e**-a + e**-b), +, inf, 0.0)`` — probabilities in negative log space.

    Probabilities multiply, and multiplying many of them underflows; storing
    ``-log p`` turns that into addition, which does not. The cost is that adding
    probabilities becomes the awkward operation, and the naive spelling of it
    breaks badly: ``-log(exp(-1000) + exp(-1000))`` evaluates ``exp(-1000)`` to
    ``0.0`` and then takes the log of zero.

    :meth:`plus` therefore factors out the smaller weight, so the exponential is
    always of a non-positive number and lands in ``(0, 1]``. It is stable at
    magnitudes where the direct form overflows in one direction and underflows in
    the other.
    """

    __slots__ = ()

    zero: float = math.inf
    one: float = 0.0
    divisible: bool = True

    def plus(self, left: float, right: float) -> float:
        """Return the weight of the summed probabilities, computed stably."""
        if left == math.inf:
            return right
        if right == math.inf:
            return left

        lower, upper = (left, right) if left < right else (right, left)

        return lower - math.log1p(math.exp(lower - upper))

    def times(self, left: float, right: float) -> float:
        """Return the weight of the product of two probabilities."""
        return left + right

    def key(self, weight: float) -> Hashable:
        """Return ``weight``, which is already canonical and hashable."""
        return weight

    def divide(self, left: float, right: float) -> float:
        """Return ``left - right``, the inverse of :meth:`times`.

        Raises
        ------
        ZeroDivisionError
            If ``right`` is :attr:`zero`, which corresponds to dividing by a
            probability of zero.
        """
        if right == math.inf:
            message = "cannot divide by the log semiring's zero (inf)"
            raise ZeroDivisionError(message)

        return left - right


class ProbabilitySemiring(_SemiringBase[float]):
    """``(+, *, 0.0, 1.0)`` — probabilities held directly.

    The readable choice, and the right one for small automata or when the numbers
    are being shown to someone. Prefer :class:`LogSemiring` when paths are long
    enough for the products to underflow.
    """

    __slots__ = ()

    zero: float = 0.0
    one: float = 1.0
    divisible: bool = True

    def plus(self, left: float, right: float) -> float:
        """Return the sum of two probabilities."""
        return left + right

    def times(self, left: float, right: float) -> float:
        """Return the product of two probabilities."""
        return left * right

    def key(self, weight: float) -> Hashable:
        """Return ``weight``, which is already canonical and hashable."""
        return weight

    def divide(self, left: float, right: float) -> float:
        """Return ``left / right``.

        Raises
        ------
        ZeroDivisionError
            If ``right`` is :attr:`zero`.
        """
        return left / right


class ViterbiSemiring(_SemiringBase[float]):
    """``(max, *, 0.0, 1.0)`` — the single most probable path.

    Identical to :class:`ProbabilitySemiring` along a path, but alternatives
    resolve to the best rather than the total. This is the difference between
    "how likely is this sequence" and "what is its most likely analysis".
    """

    __slots__ = ()

    zero: float = 0.0
    one: float = 1.0
    idempotent: bool = True
    divisible: bool = True

    def plus(self, left: float, right: float) -> float:
        """Return the more probable of two weights."""
        return left if left > right else right

    def times(self, left: float, right: float) -> float:
        """Return the product of two probabilities."""
        return left * right

    def key(self, weight: float) -> Hashable:
        """Return ``weight``, which is already canonical and hashable."""
        return weight

    def divide(self, left: float, right: float) -> float:
        """Return ``left / right``.

        Raises
        ------
        ZeroDivisionError
            If ``right`` is :attr:`zero`.
        """
        return left / right


# The annotations are the point: mypy checks each singleton against the protocol
# here, so a built-in that drifts out of conformance fails to type-check.
BOOLEAN: Semiring[bool] = BooleanSemiring()
COUNTING: Semiring[int] = CountingSemiring()
TROPICAL: Semiring[float] = TropicalSemiring()
LOG: Semiring[float] = LogSemiring()
PROBABILITY: Semiring[float] = ProbabilitySemiring()
VITERBI: Semiring[float] = ViterbiSemiring()

__all__ = [
    "BOOLEAN",
    "COUNTING",
    "LOG",
    "PROBABILITY",
    "TROPICAL",
    "VITERBI",
    "BooleanSemiring",
    "CountingSemiring",
    "LogSemiring",
    "ProbabilitySemiring",
    "Semiring",
    "TropicalSemiring",
    "ViterbiSemiring",
]
