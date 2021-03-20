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
