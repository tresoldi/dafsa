"""
test_dafsa
==========

Tests for the `dafsa` package.
"""

# Import the library itself
import dafsa

WORDS1 = ["dib", "tip", "tips", "top"]
WORDS2 = [
    "defied",
    "defies",
    "defy",
    "defying",
    "deny",
    "denying",
    "tried",
    "tries",
    "try",
    "trying",
    "tryinginges",
]
WORDS3 = [
    "ampyx",
    "abuzz",
    "athie",
    "athie",
    "athie",
    "amato",
    "amato",
    "aneto",
    "aneto",
    "aruba",
    "arrow",
    "agony",
    "altai",
    "alisa",
    "acorn",
    "abhor",
    "aurum",
    "albay",
    "arbil",
    "albin",
    "almug",
    "artha",
    "algin",
    "auric",
    "sore",
    "quilt",
    "psychotic",
    "eyes",
    "cap",
    "suit",
    "tank",
    "common",
    "lonely",
    "likeable" "language",
    "shock",
    "look",
    "pet",
    "dime",
    "small" "dusty",
    "accept",
    "nasty",
    "thrill",
    "foot",
    "steel",
    "steel",
    "steel",
    "steel",
    "abuzz",
]


def test_words1():
    trie = dafsa.Trie()
    d = dafsa.DAFSA()
    trie.add_all(WORDS1)
    d.add_all(WORDS1)

    assert len(trie) == 10
    assert len(d) == 6
    d.reduce()
    assert len(d) == 9

    for obj in [trie, d]:
        assert obj.get_word_count() == 4
        assert "dib" in obj
        assert "deny" not in obj
        assert "ampyx" not in obj


def test_words2():
    trie = dafsa.Trie()
    d = dafsa.DAFSA()
    trie.add_all(WORDS2)
    d.add_all(WORDS2)

    assert len(trie) == 32
    assert len(d) == 17
    d.reduce()
    assert len(d) == 27

    for obj in [trie, d]:
        assert obj.get_word_count() == 11
        assert "dib" not in obj
        assert "deny" in obj
        assert "ampyx" not in obj


def test_words3():
    trie = dafsa.Trie()
    d = dafsa.DAFSA()
    trie.add_all(WORDS3)
    d.add_all(WORDS3)

    assert len(trie) == 170
    assert len(d) == 144
    d.reduce()
    assert len(d) == 149

    for obj in [trie, d]:
        assert obj.get_word_count() == 48
        assert "dib" not in obj
        assert "deny" not in obj
        assert "ampyx" in obj
        assert tuple(sorted(obj.search_with_prefix("ab"))) == ("abhor", "abuzz")
        assert tuple(sorted(obj.search_with_prefix("ab", with_count=True))) == (
            ("abhor", 1),
            ("abuzz", 2),
        )
        assert tuple(sorted(obj.search("a*o*"))) == (
            "abhor",
            "acorn",
            "agony",
            "amato",
            "aneto",
            "arrow",
        )
        assert tuple(sorted(obj.search("a*o*", with_count=True))) == (
            ("abhor", 1),
            ("acorn", 1),
            ("agony", 1),
            ("amato", 2),
            ("aneto", 2),
            ("arrow", 1),
        )
        assert tuple(obj.search("su?t")) == ("suit",)
        assert tuple(obj.search("su?t", with_count=True)) == (("suit", 1),)
        assert tuple(sorted(obj.search_within_distance("arie", dist=2))) == (
            "arbil",
            "athie",
            "auric",
        )
        assert tuple(
            sorted(obj.search_within_distance("arie", dist=2, with_count=True))
        ) == (("arbil", 1), ("athie", 3), ("auric", 1))

    trie.add("athie", count=1000)
    assert tuple(
        sorted(trie.search_within_distance("arie", dist=2, with_count=True))
    ) == (("arbil", 1), ("athie", 1003), ("auric", 1))
