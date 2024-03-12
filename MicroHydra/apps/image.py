from machine import SPI, Pin
from lib import st7789py as st7789
from assets import testcard
import time

_DISPLAY_WIDTH = 240
_DISPLAY_HEIGHT = 135

tft = st7789.ST7789(
	SPI(1, baudrate=40000000, sck=Pin(36), mosi=Pin(35), miso=None),
	_DISPLAY_HEIGHT,
	_DISPLAY_WIDTH,
	reset=Pin(33, Pin.OUT),
	cs=Pin(37, Pin.OUT),
	dc=Pin(34, Pin.OUT),
	backlight=Pin(38, Pin.OUT),
	rotation=1,
	color_order=st7789.BGR
)

tft.pbitmap(testcard, 0, 0)

while True:
	time.sleep(1)