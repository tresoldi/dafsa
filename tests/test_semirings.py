"""Semiring law tests.

Every built-in is checked against the semiring axioms rather than against its own
implementation. The axioms are the whole reason this layer exists, so they are
verified property-based, over each semiring's own weight domain.

A note on floating point, because it shapes how these tests are written. The
semiring laws hold exactly over the reals; in IEEE 754 they hold only up to
rounding, and ``(a + b) + c != a + (b + c)`` for adversarially chosen floats. That
is a property of the arithmetic, not a defect in the algebra, and a test that
generated arbitrary floats would fail for reasons that teach nothing.

So the float semirings whose operations are ``+``, ``*``, ``min`` and ``max`` draw
their weights from small integers, which are exact in binary floating point and
whose sums and products stay far below ``2**53``. For those, the laws are asserted
*exactly*. :class:`~dafsa.semirings.LogSemiring` genuinely needs ``exp`` and
``log``, so it is asserted to a tolerance — and is additionally pinned by
:class:`TestLogSemiringNumerics`, which covers the numerical behaviour the
tolerance cannot see.
"""

from __future__ import annotations

import math
import operator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dafsa.semirings import (
    BOOLEAN,
    COUNTING,
    LOG,
    PROBABILITY,
    TROPICAL,
    VITERBI,
    Semiring,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def close(left: float, right: float) -> bool:
    """Compare two log-space weights, tolerating transcendental rounding."""
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)


@dataclass(frozen=True)
class Case:
    """A semiring paired with a weight domain and its equality tests.

    ``equal`` covers the axioms. ``divide_equal`` is separate because division is
    the one operation the integer-valued-float trick cannot keep exact: ``61.0``
    and ``19.0`` are both exact, but ``61 / 19`` is not representable, so
    ``times(divide(a, b), b)`` recovers ``a`` only to within rounding. Where
    ``times`` is addition the inverse is subtraction and exactness survives.
    """

    name: str
    semiring: Semiring[Any]
    values: st.SearchStrategy[Any]
    equal: Callable[[Any, Any], bool]
    divide_equal: Callable[[Any, Any], bool]


#: Small non-negative integers as floats: exact under +, *, min and max.
EXACT = st.integers(min_value=0, max_value=1000).map(float)

CASES = [
    Case("boolean", BOOLEAN, st.booleans(), operator.eq, operator.eq),
    Case(
        "counting",
        COUNTING,
        st.integers(min_value=0, max_value=1000),
        operator.eq,
        operator.eq,
    ),
    # Tropical and log divide by subtracting, which stays exact.
    Case("tropical", TROPICAL, EXACT | st.just(math.inf), operator.eq, operator.eq),
    # These two divide with `/`, which does not.
    Case("probability", PROBABILITY, EXACT, operator.eq, close),
    Case("viterbi", VITERBI, EXACT, operator.eq, close),
    Case(
        "log",
        LOG,
        st.floats(min_value=0.0, max_value=100.0) | st.just(math.inf),
        close,
        close,
    ),
]

ALL = pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])


# -- the axioms -------------------------------------------------------------


@ALL
@settings(deadline=None, max_examples=200)
@given(data=st.data())
def test_plus_is_associative(case: Case, data: st.DataObject) -> None:
    a, b, c = (data.draw(case.values) for _ in range(3))
    semiring = case.semiring

    left = semiring.plus(semiring.plus(a, b), c)
    right = semiring.plus(a, semiring.plus(b, c))

    assert case.equal(left, right)


@ALL
@settings(deadline=None, max_examples=200)
@given(data=st.data())
def test_plus_is_commutative(case: Case, data: st.DataObject) -> None:
    """Required by the axioms for every semiring, not just the commutative ones."""
    a, b = (data.draw(case.values) for _ in range(2))
    semiring = case.semiring

    assert case.equal(semiring.plus(a, b), semiring.plus(b, a))


@ALL
@settings(deadline=None, max_examples=200)
@given(data=st.data())
def test_zero_is_the_additive_identity(case: Case, data: st.DataObject) -> None:
    a = data.draw(case.values)
    semiring = case.semiring

    assert case.equal(semiring.plus(a, semiring.zero), a)
    assert case.equal(semiring.plus(semiring.zero, a), a)


@ALL
@settings(deadline=None, max_examples=200)
@given(data=st.data())
def test_times_is_associative(case: Case, data: st.DataObject) -> None:
    a, b, c = (data.draw(case.values) for _ in range(3))
    semiring = case.semiring

    left = semiring.times(semiring.times(a, b), c)
    right = semiring.times(a, semiring.times(b, c))

    assert case.equal(left, right)


@ALL
@settings(deadline=None, max_examples=200)
@given(data=st.data())
def test_one_is_the_multiplicative_identity(case: Case, data: st.DataObject) -> None:
    a = data.draw(case.values)
    semiring = case.semiring

    assert case.equal(semiring.times(a, semiring.one), a)
    assert case.equal(semiring.times(semiring.one, a), a)


@ALL
@settings(deadline=None, max_examples=200)
@given(data=st.data())
def test_zero_annihilates(case: Case, data: st.DataObject) -> None:
    a = data.draw(case.values)
    semiring = case.semiring

    assert case.equal(semiring.times(a, semiring.zero), semiring.zero)
    assert case.equal(semiring.times(semiring.zero, a), semiring.zero)


@ALL
@settings(deadline=None, max_examples=300)
@given(data=st.data())
def test_times_distributes_over_plus(case: Case, data: st.DataObject) -> None:
    """Both sides, since ``times`` is not assumed to commute."""
    a, b, c = (data.draw(case.values) for _ in range(3))
    semiring = case.semiring

    left = semiring.times(a, semiring.plus(b, c))
    assert case.equal(left, semiring.plus(semiring.times(a, b), semiring.times(a, c)))

    right = semiring.times(semiring.plus(b, c), a)
    assert case.equal(right, semiring.plus(semiring.times(b, a), semiring.times(c, a)))


# -- the flags, which algorithms will trust -------------------------------


@ALL
@settings(deadline=None, max_examples=200)
@given(data=st.data())
def test_idempotence_flag_is_accurate(case: Case, data: st.DataObject) -> None:
    """A wrong flag here silently changes results, so check it both ways."""
    a = data.draw(case.values)
    semiring = case.semiring

    if semiring.idempotent:
        assert case.equal(semiring.plus(a, a), a)


@pytest.mark.parametrize(
    ("case", "expected"),
    [(case, case.name in {"boolean", "tropical", "viterbi"}) for case in CASES],
    ids=[case.name for case in CASES],
)
def test_idempotence_flag_matches_the_operation(case: Case, *, expected: bool) -> None:
    assert case.semiring.idempotent is expected


def test_non_idempotent_semirings_really_are_not() -> None:
    """Guards the flag from being set optimistically."""
    assert COUNTING.plus(2, 2) != 2
    assert PROBABILITY.plus(2.0, 2.0) != 2.0
    assert not close(LOG.plus(1.0, 1.0), 1.0)


@ALL
@settings(deadline=None, max_examples=200)
@given(data=st.data())
def test_commutativity_flag_is_accurate(case: Case, data: st.DataObject) -> None:
    a, b = (data.draw(case.values) for _ in range(2))
    semiring = case.semiring

    if semiring.commutative:
        assert case.equal(semiring.times(a, b), semiring.times(b, a))


@ALL
@settings(deadline=None, max_examples=200)
@given(data=st.data())
def test_division_inverts_multiplication_where_claimed(case: Case, data: st.DataObject) -> None:
    a, b = (data.draw(case.values) for _ in range(2))
    semiring = case.semiring

    if not semiring.divisible or b == semiring.zero:
        return

    assert case.divide_equal(semiring.times(semiring.divide(a, b), b), a)


@ALL
def test_dividing_by_zero_is_refused(case: Case) -> None:
    semiring = case.semiring
    if not semiring.divisible:
        return

    with pytest.raises(ZeroDivisionError):
        semiring.divide(semiring.one, semiring.zero)


@ALL
def test_indivisible_semirings_refuse_division(case: Case) -> None:
    semiring = case.semiring
    if semiring.divisible:
        return

    with pytest.raises(NotImplementedError, match="not divisible"):
        semiring.divide(semiring.one, semiring.one)


@pytest.mark.parametrize(
    ("case", "expected"),
    [(case, case.name not in {"boolean", "counting"}) for case in CASES],
    ids=[case.name for case in CASES],
)
def test_divisibility_flag_matches_the_semiring(case: Case, *, expected: bool) -> None:
    """Counting is not divisible on purpose: integer division is not exact."""
    assert case.semiring.divisible is expected


# -- keys ------------------------------------------------------------------


@ALL
@settings(deadline=None, max_examples=100)
@given(data=st.data())
def test_key_is_hashable_and_agrees_with_equality(case: Case, data: st.DataObject) -> None:
    a = data.draw(case.values)
    key = case.semiring.key(a)

    hash(key)
    assert case.semiring.key(a) == key


# -- the singletons --------------------------------------------------------


@ALL
def test_singletons_are_immutable(case: Case) -> None:
    """They are shared, so an accidental write must not be possible."""
    with pytest.raises(AttributeError):
        case.semiring.zero = case.semiring.one


@ALL
def test_protocol_members_are_present_at_runtime(case: Case) -> None:
    """mypy checks conformance statically; this catches an edit made without it."""
    for member in ("zero", "one", "idempotent", "commutative", "divisible"):
        assert hasattr(case.semiring, member)
    for method in ("plus", "times", "key", "divide"):
        assert callable(getattr(case.semiring, method))


def test_repr_names_the_semiring() -> None:
    assert repr(TROPICAL) == "TropicalSemiring"
    assert repr(BOOLEAN) == "BooleanSemiring"


def test_no_star_operation_is_advertised() -> None:
    """Deliberately absent: every structure here is acyclic (see module docstring)."""
    assert not hasattr(TROPICAL, "star")


# -- identities, spelled out ----------------------------------------------


def test_identities_are_the_documented_values() -> None:
    assert (BOOLEAN.zero, BOOLEAN.one) == (False, True)
    assert (COUNTING.zero, COUNTING.one) == (0, 1)
    assert (TROPICAL.zero, TROPICAL.one) == (math.inf, 0.0)
    assert (LOG.zero, LOG.one) == (math.inf, 0.0)
    assert (PROBABILITY.zero, PROBABILITY.one) == (0.0, 1.0)
    assert (VITERBI.zero, VITERBI.one) == (0.0, 1.0)


def test_operations_are_the_documented_ones() -> None:
    assert BOOLEAN.plus(False, True) is True
    assert BOOLEAN.times(True, False) is False
    assert COUNTING.plus(2, 3) == 5
    assert COUNTING.times(2, 3) == 6
    assert TROPICAL.plus(2.0, 3.0) == 2.0
    assert TROPICAL.times(2.0, 3.0) == 5.0
    assert PROBABILITY.plus(0.25, 0.5) == 0.75
    assert PROBABILITY.times(0.5, 0.5) == 0.25
    assert VITERBI.plus(0.25, 0.5) == 0.5
    assert VITERBI.times(0.5, 0.5) == 0.25


def test_counting_weights_are_exact() -> None:
    """The point of the counting semiring: a count stays a count."""
    total = COUNTING.zero
    for _ in range(10_000):
        total = COUNTING.plus(total, 1)

    assert total == 10_000


class TestLogSemiringNumerics:
    """The log semiring's stability, which the law tests cannot observe.

    Each of these fails for the naive ``-log(exp(-a) + exp(-b))`` spelling, in one
    direction or the other.
    """

    def test_plus_of_equal_weights_halves_the_probability(self) -> None:
        # -log(e**0 + e**0) == -log 2
        assert close(LOG.plus(0.0, 0.0), -math.log(2.0))

    def test_plus_does_not_underflow_at_large_weights(self) -> None:
        """Naive: ``exp(-1000)`` is ``0.0``, so the log is taken of zero."""
        assert close(LOG.plus(1000.0, 1000.0), 1000.0 - math.log(2.0))

    def test_plus_does_not_overflow_at_large_negative_weights(self) -> None:
        """Naive: ``exp(1000)`` raises ``OverflowError``."""
        assert close(LOG.plus(-1000.0, -1000.0), -1000.0 - math.log(2.0))

    def test_plus_is_stable_across_a_wide_gap(self) -> None:
        """The smaller weight dominates; the larger contributes almost nothing."""
        assert close(LOG.plus(0.0, 800.0), 0.0)

    def test_zero_is_absorbed(self) -> None:
        assert LOG.plus(math.inf, 5.0) == 5.0
        assert LOG.plus(5.0, math.inf) == 5.0
        assert LOG.plus(math.inf, math.inf) == math.inf

    @pytest.mark.parametrize(
        ("p", "q"),
        [(0.5, 0.25), (0.1, 0.1), (0.9, 0.05), (1e-8, 1e-9), (1e-200, 1e-200)],
    )
    def test_plus_means_summing_probabilities(self, p: float, q: float) -> None:
        """The semantic check: ``plus`` in log space is ``+`` on probabilities."""
        assert close(LOG.plus(-math.log(p), -math.log(q)), -math.log(p + q))

    @pytest.mark.parametrize(("p", "q"), [(0.5, 0.25), (0.1, 0.1), (1e-100, 1e-100)])
    def test_times_means_multiplying_probabilities(self, p: float, q: float) -> None:
        assert close(LOG.times(-math.log(p), -math.log(q)), -math.log(p * q))

    def test_long_products_do_not_underflow(self) -> None:
        """A 5000-step path at p=0.5 underflows to zero in probability space."""
        weight = LOG.one
        for _ in range(5000):
            weight = LOG.times(weight, -math.log(0.5))

        assert close(weight, 5000.0 * math.log(2.0))
        assert 0.5**5000 == 0.0  # what the direct representation would have given


class TestCrossValidation:
    """Two representations of the same algebra, checked against each other.

    :class:`~dafsa.semirings.ProbabilitySemiring` and
    :class:`~dafsa.semirings.LogSemiring` express the same semiring through
    entirely separate code paths — one arithmetic, one transcendental. Agreeing on
    the same answer is a stronger signal than either passing the axioms alone,
    since a shared misreading of the axioms would not survive it.
    """

    PROBABILITIES: ClassVar[list[float]] = [0.5, 0.25, 0.125, 0.0625]

    def _fold(self, weights: list[float], *, use_log: bool) -> float:
        semiring = LOG if use_log else PROBABILITY
        total = semiring.zero
        for weight in weights:
            total = semiring.plus(total, weight)

        return total

    def test_summing_alternatives_agrees(self) -> None:
        direct = self._fold(self.PROBABILITIES, use_log=False)
        logged = self._fold([-math.log(p) for p in self.PROBABILITIES], use_log=True)

        assert close(direct, math.exp(-logged))

    def test_multiplying_along_a_path_agrees(self) -> None:
        direct = PROBABILITY.one
        logged = LOG.one
        for p in self.PROBABILITIES:
            direct = PROBABILITY.times(direct, p)
            logged = LOG.times(logged, -math.log(p))

        assert close(direct, math.exp(-logged))

    @settings(deadline=None, max_examples=100)
    @given(
        st.lists(
            st.floats(min_value=1e-6, max_value=1.0, allow_nan=False),
            min_size=1,
            max_size=8,
        )
    )
    def test_the_two_representations_agree_on_arbitrary_probabilities(
        self, probabilities: list[float]
    ) -> None:
        direct = self._fold(probabilities, use_log=False)
        logged = self._fold([-math.log(p) for p in probabilities], use_log=True)

        assert math.isclose(direct, math.exp(-logged), rel_tol=1e-9)

    def test_viterbi_never_exceeds_the_total_probability(self) -> None:
        """``max`` of a set cannot exceed its sum for non-negative weights."""
        best = VITERBI.zero
        total = PROBABILITY.zero
        for p in self.PROBABILITIES:
            best = VITERBI.plus(best, p)
            total = PROBABILITY.plus(total, p)

        assert best <= total
        assert best == max(self.PROBABILITIES)

    def test_tropical_and_viterbi_pick_the_same_alternative(self) -> None:
        """Minimising a cost and maximising its probability are the same choice."""
        probabilities = [0.5, 0.125, 0.25]
        costs = [-math.log(p) for p in probabilities]

        cheapest = TROPICAL.zero
        for cost in costs:
            cheapest = TROPICAL.plus(cheapest, cost)

        best = VITERBI.zero
        for p in probabilities:
            best = VITERBI.plus(best, p)

        assert close(cheapest, -math.log(best))
