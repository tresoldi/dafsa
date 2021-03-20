from typing import Hashable


class SeqTrie(object):
    def __init__(
        self, init=None, terminal=False, value: Hashable = "", group_end=False
    ):
        self.children = []
        self.terminal: bool = terminal
        self.value: Hashable = value
        self.group_end: bool = group_end

        # Used for minimization
        self.ref_id = None

        # TODO: do we still need this to be sorted?
        if init:
            for seq in sorted(init):
                self._add(seq)

    def _add(self, seq):
        for element in seq:
            # If `self.children` is empty (very first element) or if its element is different,
            # add a new SeqTrie
            if not self.children or self.children[-1].value != element:
                self.children.append(SeqTrie())

            # Set the reference of the current element to the last one added, and the `value`
            # as well. Note that this is very C-like programming, following the original implementation,
            # and in most cases would be frowned upon (not entirely without reason) by Python
            # purists -- nonetheless, it *is* the intended implementation
            self = self.children[-1]
            self.value = element

        # Once adding the sequence is over, the last item must be set as a terminal
        self.terminal = True

    def __iter__(self):
        # yield the children or, if there is none, this node itself
        for x in self.children:
            for y in x.__iter__():
                yield y
        yield self

    def __str__(self):
        if len(self.children) > 0:
            offspring = ":".join([str(c) for c in self.children])
        else:
            offspring = "NONE"

        return "[%s,%s,%s,%s]" % (
            self.value,
            str(self.terminal),
            str(self.group_end),
            offspring,
        )

    # TODO: copy logic from __str__, making it faster
    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __lt__(self, other):
        if len(other.children) < len(self.children):
            return True

        return hash(self) < hash(other)
