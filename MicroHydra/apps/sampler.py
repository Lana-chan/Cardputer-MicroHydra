from machine import Pin, SPI, PWM
import time, gc, micropython
from lib import keyboard
from lib import st7789py as st7789
from lib import M5Sound
from font import vga2_16x32 as font

sound = M5Sound.M5Sound()
gc.collect()
#micropython.mem_info(1)
kb = keyboard.KeyBoard()
from assets import samples

_SINE = const(\
	b'\x00\x00\x82\x09\xCE\x12\xAF\x1B\xF2\x23\x6A\x2B'\
	b'\xEB\x31\x50\x37\x7B\x3B\x55\x3E\xCC\x3F\xD9\x3F'\
	b'\x7B\x3E\xBA\x3B\xA6\x37\x55\x32\xE7\x2B\x80\x24'\
	b'\x49\x1C\x71\x13\x2B\x0A\xAB\x00\x28\xF7\xD6\xED'\
	b'\xEC\xE4\x9C\xDC\x15\xD5\x81\xCE\x07\xC9\xC5\xC4'\
	b'\xD3\xC1\x43\xC0\x1C\xC0\x61\xC1\x09\xC4\x06\xC8'\
	b'\x41\xCD\x9D\xD3\xF4\xDA\x1E\xE3\xEC\xEB\x2C\xF5'
)
SINE = memoryview(_SINE)

_SQUARE = const(\
	b'\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80'\
	b'\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80'\
	b'\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80'\
	b'\x00\x80\x00\x80\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F'\
	b'\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F'\
	b'\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F'\
	b'\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\x00\x80'
)
SQUARE = memoryview(_SQUARE)

samps = [
	samples.kick,
	samples.hat,
	samples.snare,
]

step = 0
step_count = const(16)
channel_count = const(3)
old_tick = time.ticks_ms()
beat_ticks = int(60000 / 120 / 4) # ms length of 1/16th note
channels = [[False] * step_count for _ in range(channel_count)]

channels[0][0] = True
channels[0][4] = True
channels[0][7] = True
channels[0][9] = True
channels[0][12] = True

channels[1][2] = True
channels[1][6] = True
channels[1][10] = True
channels[1][14] = True
channels[1] = [True] * step_count

channels[2][4] = True
channels[2][12] = True
 
def play_channels():
	global old_tick, step
	diff = time.ticks_diff(time.ticks_ms(), old_tick)
	if diff >= beat_ticks:
		for channel in range(channel_count):
			if bool(channels[channel][step]):
				sound.play(samps[channel], channel=channel, octave=3, volume=13)
		step = (step + 1) % step_count
		old_tick = time.ticks_ms()

def notestr(note):
	notes = ["C-", "C#", "D-", "D#", "E-", "F-", "F#", "G-", "G#", "A-", "A#", "B-"]
	return f"{notes[note%12]}{(note // 12)+1}"

while True:
	play_channels()


_DISPLAY_HEIGHT = const(135)
_DISPLAY_WIDTH = const(240)
tft = st7789.ST7789(
	SPI(1, baudrate=40000000, sck=Pin(36), mosi=Pin(35), miso=None),
	_DISPLAY_HEIGHT,
	_DISPLAY_WIDTH,
	reset=Pin(33, Pin.OUT),
	cs=Pin(37, Pin.OUT),
	dc=Pin(34, Pin.OUT),
	rotation=1,
	color_order=st7789.BGR
)
backlight = PWM(Pin(38, Pin.OUT), freq=500)
backlight.duty(256)
tft.fill_rect(0, 0, _DISPLAY_WIDTH, _DISPLAY_HEIGHT, 0)

for note in range(24,60):
	tft.fill_rect(0, 0, _DISPLAY_WIDTH, _DISPLAY_HEIGHT, 0)
	tft.text(font, notestr(note), 0, 0)
	sound.play(_SINE, note-5, 0, 13, 0, True)
	sound.play(_SINE, note, 0, 13, 1, True)
	for i in range(9,0,-1):
		time.sleep(0.03)
		sound.setvolume(i)
		sound.setvolume(i,1)
	sound.stop(0)
	sound.stop(1)

gc.collect()
micropython.mem_info(1)