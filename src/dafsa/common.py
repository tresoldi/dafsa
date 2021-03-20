from itertools import chain

def dummy():
    return 13

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