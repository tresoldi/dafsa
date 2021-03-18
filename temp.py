import os

from types import GeneratorType

import re
from contextlib import closing
from collections import deque



#from lexpy._utils import validate_expression, gen_source
#from lexpy.exceptions import InvalidWildCardExpressionError
#from lexpy.exceptions import InvalidWildCardExpressionError






###########

input_words = ['ampyx', 'abuzz', 'athie', 'athie', 'athie', 'amato', 'amato', 'aneto', 'aneto', 'aruba',
               'arrow', 'agony', 'altai', 'alisa', 'acorn', 'abhor', 'aurum', 'albay', 'arbil', 'albin',
               'almug', 'artha', 'algin', 'auric', 'sore', 'quilt', 'psychotic', 'eyes', 'cap', 'suit',
               'tank', 'common', 'lonely', 'likeable' 'language', 'shock', 'look', 'pet', 'dime', 'small' 
               'dusty', 'accept', 'nasty', 'thrill', 'foot', 'steel', 'steel', 'steel', 'steel', 'abuzz']
input_words = ["dib", "tip", "tips", "top"]
input_words = [
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


trie = Trie()
trie.add_all(input_words) # You can pass any sequence types of a file like object here
print(trie.get_word_count())
print('ampyx' in trie)
print(trie.search_with_prefix('ab'))
print(trie.search_with_prefix('ab', with_count=True))
print(trie.search('a*o*'))
print(trie.search('a*o*', with_count=True))
print(trie.search('su?t'))
print(trie.search('su?t', with_count=True))
print(trie.search_within_distance('arie', dist=2))
print(trie.search_within_distance('arie', dist=2, with_count=True))
trie.add('athie', count=1000)
print(trie.search_within_distance('arie', dist=2, with_count=True))

dawg = DAWG()
dawg.add_all(input_words)
print(len(dawg))
dawg.reduce()
print("--", dawg.get_word_count())
print(len(dawg))