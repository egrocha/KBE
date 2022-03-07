#!/usr/bin/python3
'''KBE is an experimental music keyboard'''
__version__ = "0.1"

import _thread
import argparse
import json
import os.path
import subprocess
import sys
import time
from datetime import datetime
from functools import partial
from pathlib import Path
from tkinter import *

import fluidsynth
import simpleaudio
from PIL import Image, ImageTk
from pydub import AudioSegment
from pynput.keyboard import Key, Listener

import keyboardparser
import songparser

parser = argparse.ArgumentParser()
parser.add_argument('-k', '--keyboard', help='Changes the file used for the keybinds')
parser.add_argument('-s', '--soundfont', help='Changes the soundfont that will be loaded')
parser.add_argument('-t', '--terminal', action='store_true', help='Launches the program without the interface')

pitch = 0
preset = 0
volume = 100
muted = False
keybinds = ""
soundfont = "/usr/share/sounds/sf2/FluidR3_GM.sf2"
terminal = False

key_dict = {}
shift_keys = {}
pressed_keys = {}
background_audio = {}
background_songs = {}
active_events = {}

recording = []
recording_aux = {}
recording_mode = ""
recording_start = 0
is_recording = False
metronome_on = False
first_recording = True
recording_mod = None
recording_key = None
recording_filename = ""
awaiting_record_button = False

alt_pressed = False
ctrl_pressed = False
alt_r_pressed = False
ctrl_r_pressed = False

songs = []
presets = {}
sequencers = {}
keys_to_buttons = {}

Path("audio/cache").mkdir(parents=True, exist_ok=True)

def start_sequencer():
	"""Starts the synthesizer and sequencer on program start"""
	global soundfont
	fs = fluidsynth.Synth()
	fs.start(driver='alsa')
	sfid = fs.sfload(soundfont)
	fs.program_select(0, sfid, 0, preset)
	seq = fluidsynth.Sequencer()
	synthID = seq.register_fluidsynth(fs)
	sequencers[0] = [fs, seq, synthID, sfid]

def setup_metronome():
	"""Creates and registers the metronome sequencer"""
	fs = fluidsynth.Synth()
	fs.start(driver='alsa')
	sfid = fs.sfload("./soundfonts/percussion2.sf2")
	fs.program_select(0, sfid, 0, 0)
	seq = fluidsynth.Sequencer()
	synthID = seq.register_fluidsynth(fs)
	sequencers[1] = [fs, seq, synthID, sfid]

def restart_sequencer(sf, preset):
	"""Restarts the sequencer and registers a new synthesizer ID"""
	presets[sf][preset][1].delete()
	presets[sf][preset][1] = fluidsynth.Sequencer()
	presets[sf][preset][2] = presets[sf][preset][1].register_fluidsynth(presets[sf][preset][0])

def get_file_ending(filename):
	"""Returns the file ending of the filename given as input"""
	return filename.rsplit('.', 1)[1]

def set_shiftkeys():
	"""Extracts the shift keys from the shiftkeys file"""
	data = open('keybinds/shiftkeys.json')
	data = json.load(data)
	for key in data.keys():
		shift_keys[key] = data[key]

def set_keybinds():
	"""Gets and sets the keybinds from the keybinds file.
	Checks the file's ending and sets keybinds for every modifier."""
	global soundfont, preset, songs, volume, pitch
	data = keyboardparser.pre_parse_file(keybinds)
	for mod in data.keys():
		if mod == 'config':
			for key, value in data.get(mod).items():
				if key == 'preset':
					preset = value
				if key == 'soundfont':
					soundfont = value
				if key == 'volume':
					volume = value
				if key == 'pitch':
					pitch = value
		else:
			key_dict[mod] = {}
			for key, value in data.get(mod).items():
				if type(value) == int or type(value) == list or type(value) == str:
					key_dict[mod][key] = value
				elif type(value) == dict:
					if value['type'] == 'record':
						if value.get('mode') == None:
							value['mode'] = 'replace'
					elif value['type'] == 'audio':
						value = prepare_audio_cache(value)
					elif value['type'] == 'song':
						if os.path.isfile(value['filename']):
							songs.append(value['filename'])
						else:
							print('Song file '+value['filename']+' not found!')
					if value:
						key_dict[mod][key] = value

def swap_keybinds(new_keybinds):
	"""Switches the current keybinds to the keybinds
	from a given file"""
	global keybinds
	print('Switching keybind file to ' + keybinds + ' ...')
	keybinds = new_keybinds
	set_keybinds()
	print('Keybinds switched!')

def get_song_options(options):
	"""Retrieves and then returns the options in songs"""
	global soundfont
	sf = soundfont
	preset = bpm = 0
	signature = []
	for option in options:
		if option == 'preset':
			preset = options['preset']
		elif option == 'soundfont':
			sf = options['soundfont']
		elif option == 'bpm':
			bpm = options['bpm']
		elif option == 'signature':
			signature = options['signature']
	return preset, sf, bpm, signature

def add_start(start, notes):
	"""Adds the \"start\" delay to all the events inside of 
	a song called from another song"""
	for note in notes:
		if type(note) == list:
			note[1] += start
		elif type(note) == dict and note["type"] == "song":
			note["start"] += start
	return notes

def prepare_song(key, obj, start, note_list):
	"""Attempts to get start and loop parameters from the song 
	object before playing the song.
	If values don't exist, sets preset values for them."""
	loop = 1
	pitch = 0
	try:
		if "start" in obj:
			start += obj['start']
	except:
		pass
	try:
		if "loop" in obj:
			loop = obj['loop']
	except:
		pass
	try:
		if "pitch" in obj:
			pitch = obj['pitch']
	except:
		pass
	filename = obj['filename']
	total = play_song(key, filename, start, loop, pitch, note_list)
	add_active_event(total, key, filename)
	return total

def get_preset_info(preset, sf):
	fs = presets[sf][preset][0]
	seq = presets[sf][preset][1]
	synthID = presets[sf][preset][2]
	sfid = presets[sf][preset][3]
	return [fs, seq, synthID, sfid]

#def play_song(key, filename, start, loop, pitch, note_list):
#	"""Plays a given song. Checks the file ending to 
#	define how the events in the song are extracted."""
#	total = start
#	notes, options = songparser.pre_convert_song(filename)
#	preset, sf = get_song_options(options)
#	[fs, seq, synthID, sfid] = get_preset_info(preset, sf)
#	fs.program_select(0, sfid, 0, preset)
#	total = set_song_notes(key, loop, total, notes, note_list, seq, pitch, synthID)
#	seqID = seq.register_client("me", song_callback)
#	total = seq.get_tick() + total
#	seq.timer(total, dest=seqID, data=key)
#	background_songs[key] = {"end_time": int(round(time.time() * 1000)) + total, "note_list": note_list, "preset": preset, "soundfont": sf}
#	return total

def get_song_obj_data(obj):
	loop = 1
	start = pitch = 0
	try:
		if "start" in obj:
			start += obj['start']
	except:
		pass
	try:
		if "loop" in obj:
			loop = obj['loop']
	except:
		pass
	try:
		if "pitch" in obj:
			pitch = obj['pitch']
	except:
		pass
	filename = obj['filename']
	return start, loop, pitch, filename

#def set_song_notes(key, loop, total, notes, note_list, seq, pitch, synthID):
#	for i in range(0, loop):
#		start = total
#		for j in range(0, len(notes)):
#			note = notes[j]
#			if type(note) == dict:
#				if note['type'] == 'song':
#					new_total = prepare_song(key, note, start, notes)
#				elif note['type'] == 'pause':
#					start += note['value']
#			else:
#				if i == 0:
#					note_list.append(note)
#				try:
#					channel = note[3]
#				except:
#					channel = 0
#				try:
#					velocity = note[4]
#				except:
#					velocity = 100
#				if type(note) == list and type(note[0]) == int:
#					final_note = convert_into_final_note(note[0], pitch)
#					seq.note_on(time=note[1]+start, absolute=False, channel=channel, key=final_note, velocity=velocity, dest=synthID)
#					seq.note_off(time=note[1]+note[2]+start, absolute=False, channel=channel, key=final_note, dest=synthID)
#					new_total = note[1] + note[2] + start
#				elif type(note) == list and type(note[0]) == list:
#					for n in note[0]:
#						final_note = convert_into_final_note(n, pitch)
#						seq.note_on(time=note[1]+start, absolute=False, channel=channel, key=final_note, velocity=velocity, dest=synthID)
#					for n in note[0]:
#						final_note = convert_into_final_note(n, pitch)
#						seq.note_off(time=note[1]+note[2]+start, absolute=False, channel=channel, key=final_note, dest=synthID)
#						new_total = note[1] + note[2] + start
#						if new_total > total:
#							total = new_total
#			if new_total > total:
#				total = new_total
#	return total

def convert_start_end(start, end, bpm):
	bpm = 60000/bpm
	start *= bpm
	end *= bpm
	return int(start), int(end)
	
def set_song_notes(key, loop, total, notes, note_list, seq, pitch, synthID, bpm):
	for i in range(0, loop):
		start = total
		for j in range(0, len(notes)):
			note = notes[j]
			if type(note) == dict:
				if note['type'] == 'song':
					new_total = prepare_song(key, note, start, notes)
				elif note['type'] == 'pause':
					start += note['value']
			else:
				if i == 0:
					note_list.append(note)
				try:
					channel = note[3]
				except:
					channel = 0
				try:
					velocity = note[4]
				except:
					velocity = 100
				if bpm != 0:
					note_start, note_end = convert_start_end(note[1], note[2], bpm)
				else:
					note_start = int(note[1])
					note_end = int(note[2])
				if type(note) == list and type(note[0]) == list:
					for n in note[0]:
						final_note = convert_into_final_note(n, pitch)
						seq.note_on(time=note_start + start, absolute=False, channel=channel, key=final_note, velocity=velocity, dest=synthID)
						seq.note_off(time=note_start + note_end + start, absolute=False, channel=channel, key=final_note, dest=synthID)
						new_total = note_start + note_end + start
						if new_total > total:
							total = new_total
				elif type(note) == list and type(note[0]) == int:
					final_note = convert_into_final_note(note[0], pitch)
					seq.note_on(time=note_start + start, absolute=False, channel=channel, key=final_note, velocity=velocity, dest=synthID)
					seq.note_off(time=note_start + note_end + start, absolute=False, channel=channel, key=final_note, dest=synthID)
					new_total = note_start + note_end + start
			if new_total > total:
				total = new_total
	return total

def play_song(key, obj):
	note_list = []
	start, loop, pitch, filename = get_song_obj_data(obj)
	total = start

	notes, options = songparser.pre_convert_song(filename)
	if notes:
		preset, sf, bpm, signature = get_song_options(options)
		[fs, seq, synthID, sfid] = get_preset_info(preset, sf)
		fs.program_select(0, sfid, 0, preset)
		total = set_song_notes(key, loop, total, notes, note_list, seq, pitch, synthID, bpm)
		seqID = seq.register_client("me", song_callback)
		background_songs[key] = {"end_time": int(round(time.time() * 1000)) + total, "note_list": note_list, "preset": preset, "soundfont": sf}
		total += seq.get_tick()
		seq.timer(total, dest=seqID, data=key)
		add_active_event(total, key, filename)

def song_callback(time, event, seq, data):
	if time in active_events:
		active_events.pop(time)
		refresh_active_events()

def add_active_event(total, key, filename):
	text = key + ": " + filename + "\n"
	active_events[total] = [key, text]
	refresh_active_events()

def refresh_active_events():
	event_text.delete(1.0, END)
	event_text.insert(END, 'Events\n', 'color')
	for key in active_events:
		event_text.insert(END, active_events[key][1])

def fetch_fluidsynth_info(key):
	preset = background_songs[key]['preset']
	sf = background_songs[key]['soundfont']
	fs = presets[sf][preset][0]
	note_list = background_songs[key]['note_list']
	return [preset, sf, fs, note_list]

def stop():
	"""Stops all songs that are currently playing in the background"""
	global background_songs
	for key in background_songs:
		[preset, sf, fs, note_list] = fetch_fluidsynth_info(key)
		try:
			for note in note_list:
				if type(note[0]) == int:
					fs.noteoff(0, note[0])
				elif type(note[0]) == list:
					for n in note[0]:
						fs.noteoff(0, n)
		except:
			pass
		restart_sequencer(sf, preset)
	background_songs = {}

def stop_song(key):
	"""Stops one song playing in the background. 
	The song is selected by the key given as argument"""
	[preset, sf, fs, note_list] = fetch_fluidsynth_info(key)
	try:
		for note in note_list:
			if type(note[0]) == int:
				fs.noteoff(0, note[0])
			elif type(note[0]) == list:
				for n in note[0]:
					fs.noteoff(0, n)
	except:
		pass
	del background_songs[key]
	delete_active_event(key)
	restart_sequencer(sf, preset)

def delete_active_event(key):
	global active_events
	for time in active_events.keys():
		if active_events[time][0] == key:
			active_events.pop(time)
			refresh_active_events()
			return

def prepare_audio_cache(audio):
	"""Prepares the audio cache before the program starts 
	to avoid delays in playing audio files. 
	Gets \"start\", \"end\" and \"volume\" values 
	for every file or sets them to 0 by default. 
	New cache files are created if necessary and are saved in .wav format."""
	filename = audio['filename']
	try:
		start = audio['start']
	except:
		start = 0
	try:
		end = audio['end']
	except:
		end = 0
	try:
		volume = audio['volume']
	except:
		volume = 0
	extension = filename.lower().rsplit('.', 1)[1]
	if not os.path.isfile(filename):
		print('Audio file '+filename+' not found!')
		return
	if extension != "wav" or start != 0 or end != 0 or volume != 0:
		old_filename = filename
		values = '-' + str(start) + '-' + str(end) + '-' + str(volume)
		filename = filename.rsplit('.', 1)[0]
		filename = filename.rsplit('/', 1)[1]
		filename = 'audio/cache/' + filename + values + '.wav'
		if os.path.isfile(filename):
			print('File \'' + filename + '\' loaded!')
		else:
			audio = AudioSegment.from_file(old_filename, format=extension) - 20 + volume
			if end > 0 and end > start:
				end = 1000 * end
				audio = audio[:end]
			if start > 0:
				duration = audio.duration_seconds
				start = duration - start
				start = -1000 * start
				audio = audio[start:]
			audio.export(filename, format='wav')
			print('File \'' + filename + '\' created!')
	return {'type': 'audio', 'filename': filename}

def start_background_audio(key, filename):
	"""Starts the selected audio file in the background.
	This function is called if a key is pressed and the 
	related audio file is not currently playing."""
	wave_obj = simpleaudio.WaveObject.from_wave_file(filename)
	background_audio[key] = {'object': wave_obj.play(), 'filename': filename, 'playing': True}

def stop_background_audio(key):
	"""Stops an active background audio file.
	This function is called if a key is pressed and the 
	related audio file is currently playing."""
	background_audio[key].get('object').stop()
	background_audio[key]['playing'] = False 

def await_record_button():
	global awaiting_record_button
	awaiting_record_button = True
	show_await_recording_label()

def generate_recording_filename(key):
	now = datetime.now()
	datetime_string = now.strftime("%d%m%Y%H%M%S")
	result = "songs/recordings/" + key + datetime_string + ".txt"
	return result

#def start_recording():
#	"""Starts recording the a sequence of events.
#	This function is called only if the program 
#	is not currently recording.
#	Checks the mode of recording to check if it can 
#	discard the last recording in the file."""
#	global is_recording, recording, recording_filename
#	await_record_button()
#	filename = generate_recording_filename(key)
#	is_recording = True
#	if recording_mode == 'replace':
#		recording = []
#	elif recording_mode == 'append':
#		recording = songparser.pre_convert_song(filename)
#	recording_filename = filename

def swap_event_with_song():
	global recording_mod, recording_key, recording_filename
	aux = {"type": "song", "filename": recording_filename}
	key_dict[recording_mod][recording_key] = aux

def stop_recording():
	"""Stops the current recording session. The filename
	is checked to see if the results can be saved in a JSON format
	or if they must be converted to the text format."""
	global is_recording, first_recording, preset, soundfont, recording_filename
	is_recording = False
	first_recording = True
	obj = {"type": "preset", "value": preset}
	recording.insert(0, obj)
	obj = {"type": "soundfont", "filename": soundfont}
	recording.insert(0, obj)
	swap_event_with_song()
	songparser.convert_song_to_text(recording_filename, recording)

def check_for_invalid_event(event):
	result = False
	if type(event) == dict:
		if event.get('type') != 'song' and event.get('type') != 'audio':
			result = True
		if event.get('filename') == recording_filename:
			result = True
	return result

def add_pitch_to_event(event):
	global pitch
	event += pitch
	if event > 127:
		event = 127
	elif event < 0:
		event = 0
	return event

def record_event(key, event):
	"""Adds an event given as argument to the current recording session."""
	global recording_start, recording_filename, first_recording, pitch
	if check_for_invalid_event(event):
		return
	if first_recording:
		recording_start = int(round(time.time() * 1000))
		first_recording = False
	event_start = int(round(time.time() * 1000)) - recording_start
	if type(event) == dict:
		aux = event
		aux['start'] = event_start
		recording_aux[key] = {}
		recording_aux[key]['event'] = aux
	elif type(event) == int or type(event) == list:
		if type(event) == int:
			event = add_pitch_to_event(event)
		elif type(event) == list:
			for e in event:
				e = add_pitch_to_event(e)
		recording_aux[key] = {}
		recording_aux[key]['event'] = event
		recording_aux[key]['start'] = event_start

def update_recording(key):
	"""Inserts an event into the recording list."""
	global recording_start
	aux = recording_aux[key]
	if type(aux['event']) == dict:
		end_time = int(round(time.time() * 1000)) - recording_start - aux['event']['start']
		recording.append(aux['event'])
	else:
		end_time = int(round(time.time() * 1000)) - recording_start - aux['start']
		new = []
		new.append(aux['event'])
		new.append(aux['start'])
		new.append(end_time)
		recording.append(new)
	del recording_aux[key]

def set_recording_key(mod, key):
	global recording_mod, recording_key
	recording_mod = mod
	recording_key = key

def set_recording_destination(mod, key):
	global awaiting_record_button, is_recording, recording, recording_filename
	set_recording_key(mod, key)
	awaiting_record_button = False
	is_recording = True
	recording_filename = generate_recording_filename(key)
	if recording_mode == 'replace':
		recording = []
	elif recording_mode == 'append':
		recording = songparser.pre_convert_song(recording_filename)
	hide_await_recording_label()

def start_metronome(aux):
	"""Function that starts a metronome, with
	the beat durations being calculated from the
	BPM. If a time signature is given, two different notes
	are used to set it."""
	global metronome_on
	metronome_on = True
	seq = sequencers[1][1]
	synthID = sequencers[1][2]
	start = 0
	bpm = aux.get("bpm")
	if "time" in aux:
		time = aux.get("time")
	else:
		time = 1
	duration = int(60000 / bpm)
	
	for i in range(0, 1000):
		mod = i % time
		if mod == 0:
			key = 67
		else:
			key = 68
		seq.note_on(time=start, absolute=False, channel=0, key=key, velocity=100, dest=synthID)
		seq.note_off(time=start + duration, absolute=False, channel=0, key=key, dest=synthID)
		start += duration
	change_metronome_label_bpm(bpm)

def stop_metronome():
	"""Deletes the metronome sequencer and
	replaces it with a new one"""
	global metronome_on
	metronome_on = False
	sequencers[1][1].delete()
	sequencers[1][1] = fluidsynth.Sequencer()
	sequencers[1][2] = sequencers[1][1].register_fluidsynth(sequencers[1][0])
	change_metronome_label_off()

def change_preset(new_preset):
	"""Swaps the default preset being used 
	by the keyboard"""
	global preset
	fs = sequencers[0][0]
	sfid = sequencers[0][3]
	if preset != new_preset:
		preset = new_preset
		fs.program_select(0, sfid, 0, new_preset)
		print('Preset changed to: ' + str(new_preset))

def add_pressed_keys(mod, key):
	"""Adds a key into the list of keys that are 
	currently being held."""
	global pitch
	try:
		if key in key_dict.get(mod):
			aux = key_dict.get(mod).get(key)
			if type(aux) == int:
				aux += pitch
				if aux < 0:
					aux = 0
				elif aux > 127:
					aux = 127
			elif type(aux) == list:
				new = []
				for note in aux:
					note += pitch
					if note < 0:
						note = 0
					elif note > 127:
						note = 127
					new.append(note)
				aux = new
			pressed_keys[key] = {"pressed": True, "event": aux, "mod": mod}
	except:
		pass

def convert_into_final_note(note, pitch):
	final_note = note + pitch
	if final_note < 0:
		final_note = 0
	elif final_note > 127:
		final_note = 127
	return final_note

def play_note(note):
	"""Plays a single note. The note ID is given as an argument."""
	global pitch, volume
	fs = sequencers[0][0]
	converted_volume = int(volume * 1.27)
	final_note = convert_into_final_note(note, pitch)
	fs.noteon(0, final_note, converted_volume)

def change_pitch(change):
	global pitch
	pitch += change
	if pitch > 127:
		pitch = 127
	if pitch < -127:
		pitch = -127
	change_pitch_num_label()
	print('Current pitch shift: ' + str(pitch))

def change_volume(change):
	global volume
	volume += change
	if volume < 0:
		volume = 0
	elif volume > 100:
		volume = 100
	change_volume_num_label()
	print('Current volume: ' + str(volume))

def play_event(mod, key):
	"""Receives a key for an event as argument and checks the type 
	of the event to call the appropriate auxiliary function."""
	global is_recording, volume, muted, preset, recording_mode, awaiting_record_button
	try:
		if key in key_dict.get(mod):
			aux = key_dict.get(mod).get(key)
			if aux == "exit":
				print("Exiting program...")
				_thread.interrupt_main()
				sys.exit()
				#listener.stop()
			elif aux == "mute" and muted:
				print("Keyboard unmuted!")
				muted = False
				change_volume_num_label()
			elif aux == "mute":
				print("Keyboard muted!")
				stop()
				muted = True
				show_muted_volume_icon()
			elif aux == "stop":
				stop()
			elif aux == "reload":
				set_keybinds()
			if not muted:
				if is_recording:
					record_event(key, aux)
				if awaiting_record_button:
					set_recording_destination(mod, key)
				elif type(aux) == int:
					play_note(aux)
				elif type(aux) == list:
					for note in aux:
						play_note(note)
				elif type(aux) == dict:
					if aux.get('type') == 'song':
						if key in background_songs and background_songs[key]["end_time"] > int(round(time.time() * 1000)):
							stop_song(key)
						else:
							play_song(key, aux)
							#prepare_song(key, aux, 0, [])
					elif aux.get('type') == 'audio':
						if key in background_audio:
							if background_audio[key]['object'].is_playing() == False:
								start_background_audio(key, background_audio[key]['filename'])
							else:
								stop_background_audio(key)
						else:
							start_background_audio(key, aux['filename'])
					elif aux.get('type') == 'record' and not is_recording:
						recording_mode = aux.get('mode')
						#start_recording()
						await_record_button()
						show_recording_icon()
					elif aux.get('type') == 'record':
						stop_recording()
						hide_recording_icon()
					elif aux.get('type') == 'pitch':
						change_pitch(aux.get('value'))
					elif aux.get('type') == 'volume':
						change_volume(aux.get('value'))
					elif aux.get('type') == 'preset':
						change_preset(aux.get('value'))
					elif aux.get('type') == 'metronome' and metronome_on:
						stop_metronome()
					elif aux.get('type') == 'metronome':
						start_metronome(aux)
					elif aux.get('type') == 'keybinds':
						swap_keybinds(aux.get('filename'))
					elif aux.get('type') == 'run':
						subprocess.run(aux.get('command'))
	except Exception as e:
		print('Invalid event!')
		pass

def convert_key_to_string(key):
	if format(key) == '<65027>':
		key = 'alt_r'
	else:
		try:
			key = key.char
		except:
			key = format(key).split('Key.')[1]
	if type(key) == str:
		return key

def on_press(key):
	"""Sets the modifiers, adds the keys to the pressed keys list and 
	and calls the play_event function."""
	global alt_pressed, alt_r_pressed, ctrl_pressed, ctrl_r_pressed, is_recording
	print('\n' + key + ' pressed')
	highlight_button(key)
	if key == 'alt':
		alt_pressed = True
	elif key == 'alt_r':
		alt_r_pressed = True
	elif key == 'ctrl':
		ctrl_pressed = True
	elif key == 'ctrl_r':
		ctrl_r_pressed = True
	else:
		if (not pressed_keys.get(key, False) 
			and not pressed_keys.get(key.upper(), False)
			and not pressed_keys.get(key.lower(), False)
			and not pressed_keys.get(shift_keys.get(key), False)):
			if alt_pressed:
				add_pressed_keys('alt', key)
				play_event('alt', key)
			elif alt_r_pressed:
				add_pressed_keys('alt_r', key)
				play_event('alt_r', key)
			elif ctrl_pressed:
				add_pressed_keys('ctrl', key)
				play_event('ctrl', key)
			elif ctrl_r_pressed:
				add_pressed_keys('ctrl_r', key)
				play_event('ctrl_r', key)
			else:
				add_pressed_keys('normal', key)
				play_event('normal', key)
	
def release_event(key):
	"""Stops note or chord events and removes the given key from
	the pressed keys list."""

	fs = sequencers[0][0]

	if not pressed_keys.get(key) == False:
		event = pressed_keys.get(key).get('event')
		if type(event) == list:
			for note in event:
				fs.noteoff(0, note)
		elif type(event) == int:
			fs.noteoff(0, event)
		pressed_keys[key] = False

def on_release(key): 
	"""This function is triggered when a key is released. 
	Changes the format of the key name and checks if the key 
	is one of the modifiers. If it's a normal key, triggers the
	release_event function."""
	global alt_pressed, alt_r_pressed, ctrl_pressed, ctrl_r_pressed, is_recording
	print(key + ' released')
	remove_highlight(key)
	if is_recording and key in recording_aux:
		update_recording(key)
	if key == 'alt':
		alt_pressed = False
	elif key == 'alt_r':
		alt_r_pressed = False
	elif key == 'ctrl':
		ctrl_pressed = False
	elif key == 'ctrl_r':
		ctrl_r_pressed = False
	else:
		if pressed_keys.get(key, False):
			release_event(key)		
		elif pressed_keys.get(key.upper(), False):
			release_event(key.upper())
		elif pressed_keys.get(key.lower(), False):
			release_event(key.lower())
		elif key in shift_keys and shift_keys.get(key) in pressed_keys:
			release_event(shift_keys.get(key))            

def prepare_for_press(key):
	on_press(convert_key_to_string(key))

def prepare_for_release(key):
	on_release(convert_key_to_string(key))

def start_listener():
	"""Starts the listener that is triggered when 
	keys are pressed or released. On key presses triggers 
	the on_press function and on key releases triggers the 
	on_release function"""
	global listener
	with Listener(
		on_press = prepare_for_press,
		on_release = prepare_for_release) as listener:
		listener.join()
	
def start_sequencers():
	"""Creates sequencers for each of the soundfonts
	that are being used by the application"""
	for soundfont in presets:
		for preset in presets[soundfont]:
			seq = fluidsynth.Sequencer()
			fs = fluidsynth.Synth()
			fs.start(driver='alsa')
			sfid = fs.sfload(soundfont)
			fs.program_select(preset, sfid, 0, 0)
			synthID = seq.register_fluidsynth(fs)
			presets[soundfont][preset] = [fs, seq, synthID, sfid]

def count_presets():
	"""Function that counts all the presets that are 
	used in the songs that were imported, to then 
	start sequencers for each of those presets"""
	global presets, songs, soundfont
	for song in songs:
		notes, options = songparser.pre_convert_song(song)
		preset, sf, bpm, signature = get_song_options(options)
		if sf in presets:
			presets[sf][preset] = []
		else:
			presets[sf] = {preset: []}
	start_sequencers()

def check_arguments():
	global keybinds, soundfont, terminal
	args = parser.parse_args()
	if args.keyboard is not None:
		keybinds = args.keyboard
	else:
		keybinds = 'keybinds/keybinds.txt'
	if args.soundfont is not None:
		soundfont = args.soundfont
	if args.terminal is not None:
		terminal = args.terminal

def main():
	"""Main function. Checks the given arguments to see if the 
	a different keybind file was given. Calls the set_shiftkeys, 
	set_keybinds and start_listener functions in order to start 
	the program."""
	global keybinds, soundfont
	print('Loading...')
	set_keybinds()
	start_sequencer()
	setup_metronome()
	set_shiftkeys()
	count_presets()
	print('Ready!')
	start_listener()

def highlight_button(key):
	try:
		keys_to_buttons[key].config(relief=SUNKEN)
	except:
		pass

def remove_highlight(key):
	try:
		keys_to_buttons[key].config(relief=RAISED)
	except:
		pass

def button_press(key, event):
	on_press(key)

def button_release(key, event):
	on_release(key)

def check_long_button(key):
	key_list = ["space", "shift_r"]
	if key in key_list:
		if key == "space":
			return 8
		return 2
	return 1

def check_tall_button(key):
	if key == "enter":
		return 3
	return 1

def capitalize_letters():
	return 

def lowercase_letters():
	return

def get_button_text(key):
	text = key.replace('_', ' ')
	if len(key) > 1:
		text = text.title()
	return text

def attach_button_to_frame(key, frame, i, j):
	column_span = check_long_button(key)
	row_span = check_tall_button(key)
	text = get_button_text(key)
	button = Button(frame, text=text)
	button.grid(row=i, column=j, columnspan=column_span, rowspan=row_span, sticky=N+S+E+W)
	button_press_partial = partial(button_press, key)
	button_release_partial = partial(button_release, key)
	button.bind("<ButtonPress>", button_press_partial)
	button.bind("<ButtonRelease>", button_release_partial)
	keys_to_buttons[key] = button
	return column_span

def generate_buttons():
	keyboard_list = [['esc', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'backspace'],
				     ['\\', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '\'', '«', 'enter'],
					 ['tab', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '+', '´'],
					 ['caps_lock', 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'ç', 'º', '~'],
					 ['shift', '<', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '-', 'shift_r'],
					 ['ctrl', 'cmd', 'alt', 'space', 'alt_r', 'menu', 'ctrl_r']]
	#, 'print_screen', 'scroll_lock', 'pause'
	#, 'insert', 'home', 'page_up'
	#, 'delete', 'end', 'page_down'
	#, 'left', 'up', 'down', 'right'
	i = j = 0
	for row in keyboard_list:
		j = 0
		for key in row:
			col = attach_button_to_frame(key, frame, i, j)
			j += col
		i += 1

def show_await_recording_label():
	recording_await_label.grid()

def hide_await_recording_label():
	recording_await_label.grid_remove()

def show_high_volume_icon():
	high_volume_label.grid()
	no_volume_label.grid_remove()
	medium_volume_label.grid_remove()
	low_volume_label.grid_remove()
	muted_volume_label.grid_remove()

def show_medium_volume_icon():
	medium_volume_label.grid()
	no_volume_label.grid_remove()
	high_volume_label.grid_remove()
	low_volume_label.grid_remove()
	muted_volume_label.grid_remove()

def show_low_volume_icon():
	low_volume_label.grid()
	no_volume_label.grid_remove()
	medium_volume_label.grid_remove()
	high_volume_label.grid_remove()
	muted_volume_label.grid_remove()

def show_no_volume_icon():
	no_volume_label.grid()
	muted_volume_label.grid_remove()
	low_volume_label.grid_remove()
	medium_volume_label.grid_remove()
	high_volume_label.grid_remove()

def show_muted_volume_icon():
	muted_volume_label.grid()
	no_volume_label.grid_remove()
	low_volume_label.grid_remove()
	medium_volume_label.grid_remove()
	high_volume_label.grid_remove()

def change_volume_num_label():
	global volume, muted
	volume_num_label.config(text=str(volume)+"%")
	if not muted:
		if volume >= 66:
			show_high_volume_icon()
		elif volume >= 33 and volume < 66:
			show_medium_volume_icon()
		elif volume > 0 and volume < 33:
			show_low_volume_icon()
		elif volume == 0:
			show_no_volume_icon()

def change_pitch_num_label():
	global pitch
	pitch_num_label.config(text=pitch)

def show_recording_icon():
	recording_label.grid()

def hide_recording_icon():
	recording_label.grid_remove()

def change_metronome_label_bpm(bpm):
	metronome_text_label.config(text=str(bpm)+" BPM")

def change_metronome_label_off():
	metronome_text_label.config(text="Off")

check_arguments()

if terminal:
	main()
else:
	_thread.start_new_thread(main, ())

	root = Tk()
	frame=Frame(root)
	event_frame = Frame(root)
	Grid.rowconfigure(root, 0, weight=1)
	Grid.columnconfigure(root, 0, weight=1)
	frame.grid(row=0, column=0, sticky=N+S)
	event_frame.grid(row=1, column=0, sticky=N+S)
	Grid.rowconfigure(frame, 5, weight=1)
	Grid.columnconfigure(frame, 10, weight=1)
	Grid.rowconfigure(event_frame, 0, weight=1)
	Grid.columnconfigure(event_frame, 0, weight=1)

	generate_buttons()

	for x in range(20):
		Grid.columnconfigure(frame, x, weight=0)

	for y in range(6):
		Grid.rowconfigure(frame, y, weight=0)

	event_text = Text(frame, height=10, width=50)
	scroll = Scrollbar(frame, command=event_text.yview)
	event_text.configure(yscrollcommand=scroll.set)
	event_text.tag_configure('bold_italics', font=('Arial', 12, 'bold', 'italic'))
	event_text.tag_configure('big', font=('Verdana', 20, 'bold'))
	event_text.tag_configure('color',
	                    foreground='#476042',
	                    font=('Tempus Sans ITC', 12, 'bold'))
	event_text.insert(END, 'Events\n', 'color')
	event_text.grid(row=7, column=3, columnspan=8)

	recording_await_label = Label(event_frame, text="Press button for recording destination")
	recording_await_label.grid(row=0, column=0)
	recording_await_label.grid_remove()

	icon_frame = Frame(root)
	icon_frame.grid(row=2, column=0, sticky=S+W)
	Grid.rowconfigure(icon_frame, 7, weight=1)
	Grid.columnconfigure(icon_frame, 0, weight=1)

	muted_volume_icon = Image.open("icons/mute.png")
	muted_volume_icon = muted_volume_icon.resize((30, 30), Image.ANTIALIAS)
	muted_volume_icon = ImageTk.PhotoImage(muted_volume_icon)
	muted_volume_label = Label(icon_frame, image = muted_volume_icon)
	muted_volume_label.grid(row=0, column=0)
	muted_volume_label.grid_remove()

	no_volume_icon = Image.open("icons/no_volume.png")
	no_volume_icon = no_volume_icon.resize((30, 30), Image.ANTIALIAS)
	no_volume_icon = ImageTk.PhotoImage(no_volume_icon)
	no_volume_label = Label(icon_frame, image = no_volume_icon)
	no_volume_label.grid(row=0, column=0)
	no_volume_label.grid_remove()

	low_volume_icon = Image.open("icons/low_volume.png")
	low_volume_icon = low_volume_icon.resize((30, 30), Image.ANTIALIAS)
	low_volume_icon = ImageTk.PhotoImage(low_volume_icon)
	low_volume_label = Label(icon_frame, image = low_volume_icon)
	low_volume_label.grid(row=0, column=0)
	low_volume_label.grid_remove()

	medium_volume_icon = Image.open("icons/medium_volume.png")
	medium_volume_icon = medium_volume_icon.resize((30, 30), Image.ANTIALIAS)
	medium_volume_icon = ImageTk.PhotoImage(medium_volume_icon)
	medium_volume_label = Label(icon_frame, image = medium_volume_icon)
	medium_volume_label.grid(row=0, column=0)
	medium_volume_label.grid_remove()

	high_volume_icon = Image.open("icons/high_volume.png")
	high_volume_icon = high_volume_icon.resize((30, 30), Image.ANTIALIAS)
	high_volume_icon = ImageTk.PhotoImage(high_volume_icon)
	high_volume_label = Label(icon_frame, image = high_volume_icon)
	high_volume_label.grid(row=0, column=0)

	volume_num_label = Label(icon_frame, text=str(volume)+"%")
	volume_num_label.grid(row=0, column=1)

	pitch_icon = Image.open("icons/pitch.png")
	pitch_icon = pitch_icon.resize((30, 30), Image.ANTIALIAS)
	pitch_icon = ImageTk.PhotoImage(pitch_icon)
	pitch_label = Label(icon_frame, image = pitch_icon)
	pitch_label.grid(row=0, column=2)

	pitch_num_label = Label(icon_frame, text=str(pitch))
	pitch_num_label.grid(row=0, column=3)

	metronome_icon = Image.open("icons/metronome.png")
	metronome_icon = metronome_icon.resize((30, 30), Image.ANTIALIAS)
	metronome_icon = ImageTk.PhotoImage(metronome_icon)
	metronome_label = Label(icon_frame, image = metronome_icon)
	metronome_label.grid(row=0, column=4)

	metronome_text_label = Label(icon_frame, text="Off")
	metronome_text_label.grid(row=0, column=5)

	recording_icon = Image.open("icons/recording.png")
	recording_icon = recording_icon.resize((30, 30), Image.ANTIALIAS)
	recording_icon = ImageTk.PhotoImage(recording_icon)
	recording_label = Label(icon_frame, image = recording_icon)
	recording_label.grid(row=0, column=6)
	recording_label.grid_remove()

	try:
		root.mainloop()
	except KeyboardInterrupt:
		pass

	root.quit()
