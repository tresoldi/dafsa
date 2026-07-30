"""A guard against the quadratic minimizer coming back.

1.0 found an equivalent state by scanning every state it had kept so far, and
wrapped the whole pass in a loop that restarted on any change. Its changelog
records the result: 99,171 sequences in "under 8 minutes". Replacing that scan
with a dictionary is most of what makes 2.0 fast, and a regression there would be
invisible to every other test in this suite — the answers would all still be
right.

Wall-clock thresholds are a poor guard on shared hardware, so the check that
matters here is a *ratio*: quadrupling the input should roughly quadruple the
work, and a quadratic regression would multiply it by sixteen. The absolute
budgets alongside are set loose enough to catch only a catastrophe.
"""

from __future__ import annotations

import random
import string
import time
from typing import TYPE_CHECKING, Any

import pytest

from dafsa import Dafsa, SuffixAutomaton, Trie

if TYPE_CHECKING:
    from collections.abc import Callable

# These build corpora of tens of thousands of sequences and are most of the
# suite's running time. `make test-fast` deselects them with -m "not slow".
pytestmark = pytest.mark.slow

SMALL = 4_000
LARGE = 16_000

#: Linear growth would be 4x for a 4x input. Quadratic would be 16x. The
#: threshold sits between, far enough above the linear case to absorb the noise
#: of a loaded machine and far enough below the quadratic one to catch it.
MAX_GROWTH = 10.0

#: Loose enough that only a catastrophic regression trips it.
MAX_SECONDS = 60.0


def corpus(size: int) -> list[str]:
    """Return a reproducible pseudo-lexicon of the given size."""
    generator = random.Random(size)

    return sorted(
        {
            "".join(generator.choices(string.ascii_lowercase, k=generator.randint(4, 12)))
            for _ in range(size)
        }
    )


def elapsed(work: Callable[[], Any]) -> float:
    """Return how long ``work`` took, in seconds."""
    start = time.perf_counter()
    work()

    return time.perf_counter() - start


def growth(build: Callable[[list[str]], Any]) -> float:
    """Return how much slower ``build`` gets when the input quadruples."""
    small = corpus(SMALL)
    large = corpus(LARGE)

    # A warm-up, so import-time and allocator effects do not land on the first
    # measurement and inflate the ratio.
    build(small[:500])

    small_time = max(elapsed(lambda: build(small)), 1e-6)
    large_time = elapsed(lambda: build(large))

    return large_time / small_time


def test_dafsa_construction_is_not_quadratic() -> None:
    """The register, in one number."""
    assert growth(Dafsa.from_sequences) < MAX_GROWTH


def test_trie_construction_is_not_quadratic() -> None:
    assert growth(Trie.from_sequences) < MAX_GROWTH


def test_suffix_automaton_construction_is_not_quadratic() -> None:
    """The online construction is linear; a naive one would not be."""

    def build(words: list[str]) -> Any:
        return SuffixAutomaton.from_sequence("".join(words))

    assert growth(build) < MAX_GROWTH


def test_a_large_corpus_builds_promptly() -> None:
    words = corpus(LARGE)

    assert elapsed(lambda: Dafsa.from_sequences(words)) < MAX_SECONDS


def test_minimization_actually_shrinks_a_large_corpus() -> None:
    """Speed is worthless if the automaton stopped being minimal."""
    words = corpus(LARGE)
    trie = Trie.from_sequences(words)
    dafsa = Dafsa.from_sequences(words)

    assert dafsa.num_states < trie.num_states // 2
    assert all(word in dafsa for word in words[:1000])


def test_state_signatures_stay_distinct_at_scale() -> None:
    """Minimality, checked from the frozen arrays rather than from the register."""
    dafsa = Dafsa.from_sequences(corpus(LARGE))

    seen: dict[tuple[Any, ...], int] = {}
    for state in dafsa.states():
        signature = (
            dafsa.is_final(state),
            tuple(
                (dafsa.transition_symbol(index), dafsa.transition_target(index))
                for index in dafsa.transition_indices(state)
            ),
        )
        assert signature not in seen, f"states {seen[signature]} and {state} are equal"
        seen[signature] = state


@pytest.mark.parametrize("size", [SMALL, LARGE])
def test_lookup_stays_fast(size: int) -> None:
    words = corpus(size)
    dafsa = Dafsa.from_sequences(words)

    assert elapsed(lambda: [word in dafsa for word in words]) < MAX_SECONDS


def test_unrank_does_not_depend_on_position() -> None:
    """Descending by subtree size, not counting through — the point of the counts."""
    dafsa = Dafsa.from_sequences(corpus(LARGE))
    last = len(dafsa) - 1

    early = elapsed(lambda: [dafsa.unrank(0) for _ in range(2_000)])
    late = elapsed(lambda: [dafsa.unrank(last) for _ in range(2_000)])

    # Enumeration would make the last position tens of thousands of times dearer.
    assert late < max(early, 1e-6) * 50
