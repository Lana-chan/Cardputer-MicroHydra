from lib.microhydra import hsv_to_rgb
import neopixel
from machine import Pin
import time

strip = neopixel.NeoPixel(Pin(21), 1, bpp=3)

t = 0
while True:
	t = (t+5) % 360
	r, g, b = hsv_to_rgb(t/360, 1, 1)
	strip.fill((int(r*255),int(g*255),int(b*255)))
	strip.write()
	time.sleep(0.4)