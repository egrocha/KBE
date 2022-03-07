from lark import Lark
from lark import Transformer

grammar = r"""

?start: headerfield bodyfield

headerfield: header _NL+

header: FIELD SEPARATOR COMMAND

bodyfield: noteline

noteline: notes _NL+

notes: (note)+

note: NOTE (MULTIPLIER)?

NOTE: /[a-zA-Z],?'?/
MULTIPLIER: /[0-9]/
FIELD: /[a-zA-Z]/
SEPARATOR: /:/
COMMAND: /\w+/

%import common.WORD
%import common.NUMBER
%import common.NEWLINE -> _NL
%import common.WS_INLINE
%ignore WS_INLINE
%ignore " "
"""

parser = Lark(grammar, parser="lalr", start="start")

result = ""

class TreeTransformer(Transformer):
    
    def header(self, items):
        print('header')

    def noteline(self, items):
        print('header')

def parse_file(filename):
    with open(filename, encoding='utf-8') as f:
        file_content = f.read()
        file_content = file_content + '\n'
    
    tree = parser.parse(file_content)
    TreeTransformer().transform(tree)

def __main__():
    parse_file('songs/abc/orange_in_bloom.abc')
