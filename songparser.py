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

class TreeTransformer(Transformer):
    global result, options

    def note(self, items):
        if '/' in items[2].value or '/' in items[4].value:
            result.append([int(items[0].value), convert_to_float(items[2].value), convert_to_float(items[4].value)])
        else:
            result.append([int(items[0].value), int(items[2].value), int(items[4].value)])

    def chord(self, items):
        notes = []
        for i in range(0, len(items)):
            if items[i] == "start" or items[i] == "s":
                break
            notes.append(int(items[i]))
        if '/' in items[i+1].value or '/' in items[i+3].value:
            result.append([notes, convert_to_float(items[i+1].value), convert_to_float(items[i+3].value)])
        else:
            result.append([notes, int(items[i+1].value), int(items[i+3].value)])
        
    def song(self, items):
        song = {}
        extension = items[0].value.rsplit(".", 1)[1]
        if extension == "json" or extension == "txt":
            song["type"] = "song"
            song["filename"] = items[0].value
            if '/' in items[2].value or '/' in items[2].value:
                song["start"] = convert_to_float(items[2].value)
            else:
                song["start"] = int(items[2].value)
            try:
                if items[3].value == "loop" or items[3].value == "l":
                    song["loop"] = int(items[4].value)
            except:
                pass
            result.append(song)

    def pause(self, items):
        if '/' in items[1].value or '/' in items[1].value:
            result.append({"type": "pause", "value": convert_to_float(items[1].value)})
        else:
            result.append({"type": "pause", "value": int(items[1].value)})

    def preset(self, items):
        options["preset"] = int(items[1].value) 

    def soundfont(self, items):
        options["soundfont"] = items[1].value

    def bpm(self, items):
        options["bpm"] = int(items[1].value)

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
        return whole - fraction if whole < 0 else whole + fraction

def convert_song_to_text(filename, object):
    output = ""

    for item in object:
        if type(item) == list:
            if type(item[0]) == int:
                output += str(item[0]) + " start " + str(item[1]) + " duration " + str(item[2]) + "\n"
            elif type(item[0]) == list:
                for note in item[0]:
                    output += str(note) + " "
                output += "start " + str(item[1]) + " duration " + str(item[2]) + "\n"
        elif type(item) == dict:
            if item["type"] == "song":
                output += item["filename"] + " start " + str(item["start"]) + " loop " + str(item["loop"]) + "\n"
            elif item["type"] == "preset":
                output += "preset " + str(item["value"]) + "\n"
            elif item["type"] == "soundfont":
                output += "soundfont " + str(item["filename"]) + "\n"

    output_file = open(filename, "w")
    output_file.write(output)
    output_file.close()

def convert_song(filename):
    global result, options
    
    with open(filename, encoding="utf-8") as f:
        file_content = f.read()
        file_content = file_content + "\n"
    
    tree = parser.parse(file_content)
    TreeTransformer().transform(tree)

def pre_convert_song(filename):
    global result, options
    result = []
    options = {}
    convert_song(filename)
    return result, options
