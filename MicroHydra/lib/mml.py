# ~*~ coding: utf-8 ~*~
#-
# Copyright © 2016, 2021
#       mirabilos <m@mirbsd.org>
# Copyright © 2013, 2016
#       Dominik George <nik@naturalnet.de>
# Copyright © 2013
#       Eike Tim Jesinghaus <eike@naturalnet.de>
#-
# Provided that these terms and disclaimer and all copyright notices
# are retained or reproduced in an accompanying document, permission
# is granted to deal in this work without restriction, including un‐
# limited rights to use, publicly perform, distribute, sell, modify,
# merge, give away, or sublicence.
#
# This work is provided “AS IS” and WITHOUT WARRANTY of any kind, to
# the utmost extent permitted by applicable law, neither express nor
# implied; without malicious intent or gross negligence. In no event
# may a licensor, author or contributor be held liable for indirect,
# direct, other damage, loss, or other issues arising in any way out
# of dealing in the work, even if advised of the possibility of such
# damage or existence of a defect, except proven that it results out
# of said person’s immediate fault when using the work as intended.

""" Functions and data to deal with Music Macro Language parsing
and conversion into frequency and duration tuples, as well as
generic tools for dealing with MML.
"""

# Pre-calculated note frequencies
#
# The list comprehension creates a list of 84 frequencies
# from C2 (C, o0c) to B8 (h''''', o6b) mapping the MML note
# number (minus one) to its 12-EDO, A=440 Hz, frequency
#_MML_NOTE2FREQ = [(440.0 * pow(2, (n - 33) / 12.)) for n in range(0, 84)]

# Note offsets
# Map pitch names to half-tone steps from the current C
_MML_NAME2STEP = {
	'C': 0,
	'D': 2,
	'E': 4,
	'F': 5,
	'G': 7,
	'A': 9,
	'B': 11
}

# Map half-tone steps to valid/normalised MML pitch inputs
_MML_STEP2NAME_IS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
_MML_STEP2NAME_ES = ['C', 'D-', 'D', 'E-', 'E', 'F', 'G-', 'G', 'A-', 'A', 'B-', 'B']

# Note offsets, reverse
#
# Map MML note numbers (minus one) to tuple (MML octave, pitch name,
# accidental sign)
#
# For enharmonic equivalents, ♯ is used for all half-tones except B♭
# (common guess)
MML_NOTE2PITCH = [item for sublist in
	[
		[
			(octave, 'C', u'♮'),
			(octave, 'C', u'♯'),
			(octave, 'D', u'♮'),
			(octave, 'D', u'♯'),
			(octave, 'E', u'♮'),
			(octave, 'F', u'♮'),
			(octave, 'F', u'♯'),
			(octave, 'G', u'♮'),
			(octave, 'G', u'♯'),
			(octave, 'A', u'♮'),
			(octave, 'B', u'♭'),
			(octave, 'B', u'♮')]
		for octave in range(0, 7)]
	for item in sublist
]

def _addtoplaylist(res, freq, dur):
	""" Merge note or pause onto playlist

	Helper function to merge a note or pause onto the playlist

	Important: may only be called from mml_play because it
	directly manipulates the result playlist, which only
	overridable functions are permitted to do; this isn’t one.

	 res - the result playlist
	 freq - the frequency (0 to pause)
	 dur - the length
	"""

	# simple case
	if len(res) == 0 or not isinstance(res[-1], tuple):
		res.append((freq, dur))
		return
	# merge same-frequency occurrences
	prec = res.pop()
	if prec[0] == freq:
		res.append((freq, prec[1] + dur))
		return
	# oops, no; restore preceding element and add a new one
	res.append(prec)
	res.append((freq, dur))

def _mml_barline(res):
	""" Add bar line to playlist

	Helper function to merge a synchronisation mark onto the playlist
	(may be overridden)

	 res - the result playlist
	"""

	if len(res) > 0 and res[-1] != 1:
		res.append(1)

def _mml_play(res, bpm, art, note, length, dots, extra):
	""" Play a note or pause

	Helper function to play an MML note after parsing sustain dots
	by adding it onto the result playlist (may be overridden)

	The “extra” information are not read by this implementation but
	must be passed by all callers! Values are:

	 • tuple(mmloctave, basenote, accidentalsign)
	 ‣ mmloctave is int, 0‥6
	   ‣ basenote ∈ ("C", "D", "E", "F", "G", "A", "B")
	   ‣ accidentalsign ∈ (u'♭', u'♮', u'♯')
	 • int(-1) to play a pause (rest)
	 • int mmlnote-1, 0‥83
	   ‣ tuple form preferred as this involves guessing the accidental sign

	 res - the result playlist
	 bpm - the current tempo
	 art - the current articulation
	 note - the note number minus 1, or -1 for pause
	 length - the time value (length) to play
	 dots - amount of sustain dots
	 extra - additional information for export
	"""

	# calculate duration
	length /= 1.5**dots
	duration = ((60.0 / bpm) * 4) / length

	# articulate note
	if note == -1:
		# pause
		_addtoplaylist(res, 0, duration)
	elif art == 'L':
		# legato
		_addtoplaylist(res, note, duration)
	else:
		# normal or staccato
		if art == 'N':
			part = 7.0/8
		else:
			part = 3.0/4
		_addtoplaylist(res, note, duration * part)
		_addtoplaylist(res, 0, duration - duration * part)

def _getint(macro, minval, maxval, defval):
	""" Parse an MML number

	Parses an MML number (positive) with bounds checking

	 macro - the MML input list
	 minval - the minimum allowed value
	 maxval - the maximum allowed value
	 defval - the default value to use if bounds are exceeded

	 Returns an int, or defval.
	"""

	if not (macro and macro[0].isdigit()):
		return defval
	num = ""
	while macro and macro[0].isdigit():
		num += macro.pop(0)
	i = int(num)
	if i < minval or i > maxval:
		return defval
	return i

def mml(macro, _nplay=None, _barline=None, _mmltrk=None):
	""" Parse a string in the "music macro language"

	The resulting playlist is ordinarily a list of (frequency, duration)
	tuples, but the two overridable functions are the only ones modifying
	it, so it can be anything these do.

	 macro - string in the music macro language
	 _nplay - a function playing a note or pause, or None (_mml_play)
	 _barline - a function playing a bar line, or None (_mml_barline)
	 _mmltrk - a function called with a normalised form of the MML (None)

	Returns the playlist.
	"""

	# overridden functions
	if _nplay is None:
		_nplay = _mml_play
	if _barline is None:
		_barline = _mml_barline
	# result playlist, may be manipulated only by overridable functions
	res = []

	# state machine variables
	art = 'N'
	bpm = 120
	octave = 4
	octave_tracking = False
	octave_tracking_onhold = True
	octave_tracking_last_note = 12 * octave
	timevalue = 4
	# result normalised MML
	normml = ["O4L4T120MN "]

	# normalise macro string, create input list
	macro = macro.upper()
	macro = macro.replace(" ", "")
	macro = list(macro)

	# helper function to parse sustain dots and call _nplay
	def _play(macro, normml, res, bpm, art, note, length, extra):
		# parse sustain dots
		ndots = 0
		while macro and macro[0] == ".":
			macro.pop(0)
			ndots += 1
			normml[0] += "."
		# play the note or append to a playlist
		_nplay(res, bpm, art, note, length, ndots, extra)

	while macro:
		char = macro.pop(0)

		if char in _MML_NAME2STEP.keys():
			# base note
			bnote = char
			note = 12 * octave + _MML_NAME2STEP[char]
			acc = u'♮'
			# accidental sign
			if macro and macro[0] in ("#", "+"):
				if note < 83:
					note += 1
					acc = u'♯'
					bnote = _MML_STEP2NAME_IS[note % 12]
					if bnote == 'C':
						normml[0] += ">"
				macro.pop(0)
			elif macro and macro[0] == "-":
				if note > 0:
					note -= 1
					acc = u'♭'
					bnote = _MML_STEP2NAME_ES[note % 12]
					if bnote == 'B':
						normml[0] += "<"
				macro.pop(0)

			# octave tracking implementation
			if octave_tracking and not octave_tracking_onhold:
				if (note < 72) and (abs(note - octave_tracking_last_note) >
				  abs(note + 12 - octave_tracking_last_note)):
					normml[0] += ">"
					octave += 1
					note += 12
				if (note >= 12) and (abs(note - octave_tracking_last_note) >
				  abs((note - 12) - octave_tracking_last_note)):
					normml[0] += "<"
					octave -= 1
					note -= 12
			octave_tracking_onhold = False
			octave_tracking_last_note = note

			# final calculated pitch
			extra = (octave, char, acc)
			normml[0] += bnote

			# length
			_length = _getint(macro, 1, 64, -1)
			if _length != -1:
				normml[0] += str(_length)
			else:
				_length = timevalue

			# parse sustain dots, append note to playlist
			_play(macro, normml, res, bpm, art, note, _length, extra)

		elif char == "L":
			timevalue = _getint(macro, 1, 64, 4)
			normml[0] += "L" + str(timevalue)

		elif char == "M":
			if macro:
				char = macro.pop(0)
				if char in ("L", "N", "S"):
					art = char
					normml[0] += "M" + char

		elif char == "N":
			note = _getint(macro, 0, 84, 0)
			normml[0] += "N" + str(note)
			note -= 1
			_play(macro, normml, res, bpm, art, note, timevalue, note)

		elif char == "O":
			if macro and macro[0] == "N":
				octave_tracking = False
				octave_tracking_onhold = False
				macro.pop(0)
			elif macro and macro[0] == "L":
				octave_tracking = True
				macro.pop(0)
			else:
				octave = _getint(macro, 0, 6, 4)
				normml[0] += "O" + str(octave)
				octave_tracking_onhold = True

		elif char == ">":
			if octave < 6:
				octave += 1
				normml[0] += char
			octave_tracking_onhold = True

		elif char == "<":
			if octave > 0:
				octave -= 1
				normml[0] += char
			octave_tracking_onhold = True

		elif char == "P" or char == "R":
			_length = _getint(macro, 1, 64, timevalue)
			normml[0] += "P" + str(_length)
			_play(macro, normml, res, bpm, art, -1, _length, -1)

		elif char == "T":
			bpm = _getint(macro, 32, 255, 120)
			normml[0] += "T" + str(bpm)

		elif char == "|":
			normml[0] += " "
			_barline(res)

		elif char == "X":
			while macro and macro[0] != ";":
				macro.pop(0)

	if _mmltrk is not None:
		_mmltrk(normml[0].replace('<>', '').replace('><', '').strip())
	return res
