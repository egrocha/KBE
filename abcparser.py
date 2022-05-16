from lark import Lark
from lark import Transformer

grammar = r"""

?start: ((_NL+)? line _NL+)*

line: noteline
    | headerline

noteline: note+

note: FIELD MOD1? MOD2? 

MOD1: /\,/
MOD2: /\'/

headerline: FIELD SEPARATOR COMMAND

NOTE: /[a-zA-Z],?'?/
MULTIPLIER: /[0-9]/
FIELD: /[a-zA-Z]/
SEPARATOR: /:/
COMMAND: /.+/

%import common.WORD
%import common.NUMBER
%import common.NEWLINE -> _NL
%import common.WS_INLINE
%ignore WS_INLINE
%ignore " "
"""

parser = Lark(grammar, parser="lalr", start="start")

result = []
options = {}
start = 0
note_relation = {'G,': 60, 'A,': 61, 'B,': 62, 'C': 63, 'D': 64, 'E': 65, 'F': 66, 
                 'G': 67, 'A': 68, 'B': 69, 'c': 70, 'd': 71, 'e': 72, 'f': 73, 
                 'g': 74, 'a': 75, 'b': 76, 'c\'': 77, 'd\'': 78}

class TreeTransformer(Transformer):

    def note(self, items):
        print(items)
        global start
        note = items[0].value
        note += get_note_mods(items)
        note = get_related_note(note)
        obj = get_start_and_duration(note)
        result.append(obj)

    def headerline(self, items):
        if items[0].value == 'Q':
            options['bpm'] = int(items[2].value.split('=')[1])
        else:
            print(items[2].value)

def get_start_and_duration(note):
    global start
    #TODO: dev
    duration = 1
    result = [note, start, duration]
    start += duration
    return result

def get_note_mods(items):
    try:
        mod = items[1].value
        return mod
    except:
        return ""

def get_related_note(note):
    try:
        note = note_relation[note]
        return note
    except:
        return 0
    
def convert_letter_to_note(letter):
    return note_relation[letter]

def convert_to_float(fraction):
    try:
        return float(fraction)
    except ValueError:
        num, denom = fraction.split('/')
        try:
            leading, num = num.split(' ')
            whole = float(leading)
        except ValueError:
            whole = 0
        fraction = float(num) / float(denom)
        return whole - fraction if whole < 0 else whole + fraction3

def parse_file(filename):
    with open(filename, encoding='utf-8') as f:
        file_content = f.read()
        file_content = file_content + '\n'
    
    tree = parser.parse(file_content)
    TreeTransformer().transform(tree)

def main():
    parse_file('songs/abc/orange_in_bloom.abc')
    print(result) 
    print(options)
    return result, options

if __name__ == '__main__':
    main()
