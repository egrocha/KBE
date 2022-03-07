from lark import Lark
from lark import Transformer

grammar = r"""

?start: ((_NL+)? line _NL+)*

line: config
    | assignment

config: myimport
      | mymod
      | defaultpreset
      | defaultsoundfont
      | defaultvolume
      | defaultpitch

assignment: note 
          | chord
          | volume
          | pitch
          | record
          | song
          | audio
          | exit
          | mute
          | preset
          | stop
          | reload
          | metronome
          | keybinds
          | run

myimport: IMPORT FILENAME
mymod: ALT | ALTR | CTRL | CTRLR | NORMAL
defaultpreset: DEFAULT PRESET NUMBER
defaultsoundfont: DEFAULT SOUNDFONT FILENAME
defaultvolume: DEFAULT VOLUME NUMBER 
defaultpitch: DEFAULT PITCH NUMBER

note: KEY NUMBER
chord: KEY NUMBER (NUMBER)+
volume: KEY VOLUME NEGNUMBER
pitch: KEY PITCH NEGNUMBER
record: KEY RECORD OPTION? FILENAME?
song: KEY SONG FILENAME (LOOP NUMBER)? (PITCH NEGNUMBER)?
audio: KEY AUDIO FILENAME (START NUMBER)? (END NUMBER)? (VOLUME NEGNUMBER)?
exit: KEY EXIT
mute: KEY MUTE
preset: KEY PRESET NUMBER
stop: KEY STOP
reload: KEY RELOAD
metronome: KEY METRONOME NUMBER (TIME NUMBER)?
keybinds: KEY KEYBINDS FILENAME
run: KEY RUN (COMMAND)+

COMMENT: /\/\/.*\n+/i
IMPORT: "import"
ALT: "alt"
ALTR: "alt_r"
CTRL: "ctrl"
CTRLR: "ctrl_r"
NORMAL: "normal"
DEFAULT: "default"
SOUNDFONT: "soundfont"

KEY: /[^ \n]+/
PRESET: /preset/i
VOLUME: /volume|v/i
PITCH: /pitch/i
RECORD: /record/i
OPTION: /append/i
FILENAME: /[\w\/.,-]+\.[A-Za-z0-9]+/
SONG: /song/i
LOOP: /loop|l/i
AUDIO: /audio|a/i
START: /start|s/i
END: /end|e/i
EXIT: /exit/i
MUTE: /mute/i
STOP: /stop/i
RELOAD: /reload/i
METRONOME: /metronome/i
TIME: /time|t/i
KEYBINDS: /keybinds|k/i
NEGNUMBER: /(\+|-)?[0-9]+/
RUN: /run/i
COMMAND: /[^ \n]+/

%import common.WORD
%import common.NUMBER
%import common.NEWLINE -> _NL
%import common.WS_INLINE
%ignore WS_INLINE
%ignore COMMENT
%ignore " "
"""
parser = Lark(grammar, parser="lalr", start="start")

result = {}
result["normal"] = {}
result["ctrl"] = {}
result["ctrl_r"] = {}
result["alt"] = {}
result["alt_r"] = {}

mod = "normal"
import_list = []

class TreeTransformer(Transformer):
    global mod, import_list

    def note(self, items):
        result[mod][items[0].value] = int(items[1].value)

    def chord(self, items):
        notes = []
        for i in range(1,len(items)):
            notes.append(int(items[i].value))
        result[mod][items[0].value] = notes

    def volume(self, items):
        result[mod][items[0].value] = {"type": "volume", "value": int(items[2].value)}

    def pitch(self, items):
        result[mod][items[0].value] = {"type": "pitch", "value": int(items[2].value)}

    def record(self, items):
        result[mod][items[0].value] = {"type": "record"}
        #if items[2].value == "append":
        #    result[mod][items[0].value]["mode"] = "append"
        #elif items[2]:
        #    result[mod][items[0].value] = {"type": "record", "filename": items[2].value}

    def song(self, items):
        result[mod][items[0].value] = {"type": "song", "filename": items[2].value}
        for i in range(2, len(items)):
            if items[i] == "loop" or items[i] == "l":
                result[mod][items[0].value]["loop"] = int(items[i+1].value)
            elif items[i] == "pitch" or items[i] == "p":
                result[mod][items[0].value]["pitch"] = int(items[i+1].value)
    
    def audio(self, items):
        result[mod][items[0].value] = {"type": "audio", "filename": items[2].value}
        for i in range(2, len(items)):
            if items[i] == "start" or items[i] == "s":
                result[mod][items[0].value]["start"] = int(items[i+1].value)
            elif items[i] == "end" or items[i] == "e":
                result[mod][items[0].value]["end"] = int(items[i+1].value)
            elif items[i] == "volume" or items[i] == "v":
                result[mod][items[0].value]["volume"] = int(items[i+1].value)

    def exit(self, items):
        result[mod][items[0].value] = "exit"

    def mute(self, items):
        result[mod][items[0].value] = "mute"

    def preset(self, items):
        result[mod][items[0].value] = {"type": "preset", "value": int(items[2].value)}

    def stop(self, items):
        result[mod][items[0].value] = "stop"

    def reload(self, items):
        result[mod][items[0].value] = "reload"
    
    def metronome(self, items):
        result[mod][items[0].value] = {"type": "metronome", "bpm": int(items[2].value)}
        try:
            result[mod][items[0].value]["time"] = int(items[4].value)
        except:
            pass
    
    def keybinds(self, items):
        result[mod][items[0].value] = {"type": "keybinds", "filename": items[2].value}

    def myimport(self, items):
        aux = items[1].value
        if aux not in import_list:
            import_list.append(aux)
            parse_file(aux)

    def mymod(self, items):
        global mod
        mod = items[0].value
    
    def run(self, items):
        command = []
        for i in range(2, len(items)):
            command.append(items[i])
        result[mod][items[0].value] = {"type": "run", "command": command}

    def defaultpreset(self, items):
        result["config"]["preset"] = int(items[2].value)
    
    def defaultsoundfont(self, items):
        result["config"]["soundfont"] = items[2].value

    def defaultvolume(self, items):
        result["config"]["volume"] = int(items[2].value)

    def defaultpitch(self, items):
        result["config"]["pitch"] = int(items[2].value)

def parse_file(filename):
    global mod
    mod = "normal"

    with open(filename, encoding="utf-8") as f:
        file_content = f.read()
        file_content = file_content + "\n"
    
    tree = parser.parse(file_content)
    TreeTransformer().transform(tree)
    mod = "normal"

def pre_parse_file(filename):
    global import_list
    import_list = []

    result["config"] = {}
    result["normal"] = {}
    result["ctrl"] = {}
    result["ctrl_r"] = {}
    result["alt"] = {}
    result["alt_r"] = {}

    parse_file(filename)

    return result
