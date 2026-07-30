"""Measure construction and query cost at a size where the shape of the curve shows.

Run with ``python benchmarks/run.py``. The numbers quoted in ``ARCHITECTURE.md`` come
from here, so that a claim in the design document can be re-checked rather than
taken on trust.

The comparison worth keeping in view is 1.0's own changelog, which records 99,171
sequences taking "under 8 minutes" — the cost of finding an equivalent state by
scanning every state seen so far instead of looking it up.
"""

from __future__ import annotations

import random
import string
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dafsa import Dafsa, SuffixAutomaton, Trie
from dafsa.semirings import COUNTING

if TYPE_CHECKING:
    from collections.abc import Callable

CORPUS_SIZE = 100_000
SEED = 7


def corpus(size: int = CORPUS_SIZE) -> list[str]:
    """Return a reproducible pseudo-lexicon."""
    generator = random.Random(SEED)

    return sorted(
        {
            "".join(generator.choices(string.ascii_lowercase, k=generator.randint(3, 10)))
            for _ in range(size)
        }
    )


def timed(label: str, work: Callable[[], Any]) -> Any:
    """Run ``work``, print how long it took, and return its result."""
    start = time.perf_counter()
    result = work()
    print(f"{label:<34}{time.perf_counter() - start:7.2f}s")

    return result


def main() -> None:
    """Run the benchmarks."""
    words = corpus()
    print(f"{len(words)} sequences, {sum(map(len, words))} tokens\n")

    print("construction")
    trie = timed("  Trie.from_sequences", lambda: Trie.from_sequences(words))
    dafsa = timed("  Dafsa.from_sequences", lambda: Dafsa.from_sequences(words))
    timed(
        "  Dafsa.from_sequences (counting)",
        lambda: Dafsa.from_sequences(words, semiring=COUNTING),
    )
    compacted = timed("  Dafsa.compact", dafsa.compact)

    print("\nsize")
    for name, automaton in (
        ("  Trie", trie),
        ("  Dafsa", dafsa),
        ("  CompactDafsa", compacted),
    ):
        print(
            f"{name:<34}{automaton.num_states:>9} states{automaton.num_transitions:>10} transitions"
        )

    print("\nqueries")
    timed("  membership, every word", lambda: [w in dafsa for w in words])
    timed("  len (builds suffix counts)", lambda: len(dafsa))
    timed("  len (cached)", lambda: len(dafsa))
    timed("  ordered iteration", lambda: list(dafsa))
    timed("  rank, every word", lambda: [dafsa.rank(w) for w in words])
    timed(
        "  unrank, every position",
        lambda: [dafsa.unrank(i) for i in range(len(dafsa))],
    )

    print("\nsubstring index")
    text = "".join(words[:2000])
    index = timed(
        f"  SuffixAutomaton ({len(text)} tokens)",
        lambda: SuffixAutomaton.from_sequence(text),
    )
    print(f"{'  states':<34}{index.num_states:>9}")
    timed("  num_substrings", index.num_substrings)


if __name__ == "__main__":
    main()
