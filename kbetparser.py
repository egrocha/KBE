from lark import Lark
from lark import Transformer

grammar = r"""

?start: ((_NL+)? event _NL+)*

event: note
     | chord
     | song
     | preset
     | soundfont
     | bpm

note: NUMBER START NUMORSIG DURATION NUMORSIG
chord: NUMBER (NUMBER)+ START NUMORSIG DURATION NUMORSIG
song: FILENAME START NUMORSIG (LOOP NUMBER)?
pause: PAUSE DURATION NUMORSIG
preset: PRESET NUMBER
soundfont: SOUNDFONT FILENAME
bpm: BPM NUMBER

COMMENT: /\/\/.*\n+/
FILENAME: /[\w\/.,-]+\.[A-Za-z0-9]+/
LOOP: /loop|l/i
START: /start|s/i
DURATION: /duration|d/i
PAUSE: /pause/i
PRESET: /preset|p/i
SOUNDFONT: /soundfont/i
BPM: /bpm/i
NUMORSIG: /[0-9]+(\/[0-9]+)?/

%import common.WORD
%import common.NUMBER
%import common.NEWLINE -> _NL
%import common.WS_INLINE
%ignore WS_INLINE
%ignore COMMENT
%ignore " "
"""
parser = Lark(grammar, parser="lalr", start="start")

result = []
options = {}
note_relation = {60: 'G,', 61: 'A,', 62: 'B,', 63: 'C', 64: 'D', 65: 'E', 66: 'F', 
                 67: 'G', 68: 'A', 69: 'B', 70: 'c', 71: 'd', 72: 'e', 73: 'f', 
                 74: 'g', 75: 'a', 76: 'b', 77: 'c\'', 78: 'd\''}

class TreeTransformer(Transformer):
    
    def note(self, items):
        print('note')

def parse_file(filename):
    global result, options
    
    with open(filename, encoding="utf-8") as f:
        file_content = f.read()
        file_content = file_content + "\n"
    
    tree = parser.parse(file_content)
    TreeTransformer().transform(tree)

def main():
    parse_file('songs/test.txt')
    print(result)
    print(options)
    return result, options

if __name__ == '__main__':
    main()
