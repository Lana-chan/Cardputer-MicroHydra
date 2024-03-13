from lib.microhydra import hsv_to_rgb
from neopixel import NeoPixel
from machine import Pin
import time

strip = NeoPixel(Pin(21), 1, bpp=3)

t = 0
while True:
	t = (t+1) % 360
	r, g, b = hsv_to_rgb(t/360, 1, 1)
	strip[0]((int(r*255),int(g*255),int(b*255)))
	strip.write()
	time.sleep_ms(100)