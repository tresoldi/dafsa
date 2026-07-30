"""Type aliases shared across the library.

Tokens are the units a caller works with — characters, phonemes, words, feature
bundles, anything hashable. Symbols are the dense integers a token maps to
inside an automaton, and states are the dense integers identifying its states.
Keeping the three distinct in signatures makes it obvious which side of the
:class:`~dafsa.alphabet.Alphabet` boundary a value belongs to.
"""

from __future__ import annotations

from collections.abc import Hashable
from typing import TypeAlias

#: A unit of a sequence, as supplied by the caller. Must be hashable.
Token: TypeAlias = Hashable

#: The dense integer an alphabet assigns to a token.
Symbol: TypeAlias = int

#: The dense integer identifying a state of an automaton.
State: TypeAlias = int

#: The state every traversal starts from. Canonical renumbering guarantees that
#: the root is state zero, so this is a fact about frozen automata rather than a
#: convention they happen to follow.
ROOT: State = 0

__all__ = ["ROOT", "State", "Symbol", "Token"]
