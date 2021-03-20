from itertools import chain


def extract_words(array, node_idx, carry=""):
    node = array[node_idx]
    if not node.value:
        return
    while True:
        for x in extract_words(array, node.children, carry + node.value):
            yield x
        if node.terminal:
            yield carry + node.value
        if node.group_end:
            break
        node_idx += 1
        node = array[node_idx]


def get_global_elements(sequences):
    return sorted(
        set(
            chain.from_iterable(
                [[element for element in sequence] for sequence in sequences]
            )
        )
    )


def read_words(filename):
    lines = open(filename, encoding="utf-8").readlines()
    lines = [line.strip() for line in lines]
    if " " in lines[0]:
        lines = tuple([tuple(w.split()) for w in lines])

    return tuple(lines)
