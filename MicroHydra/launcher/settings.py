from machine import Pin, SPI
import machine
import time, os, json, math
from lib import keyboard, beeper
from lib import st7789py as st7789
from lib import microhydra as mh
from font import vga2_16x32 as font
from font import vga1_8x16 as fontsmall


"""

MicroHydra settings!

Updated for version 0.6:
Distinguished Confirm button from other menu options, added scroll bar, added wrap-around for settings scrolling.
Fixed issue with double-input when returning from menu option.
Added ESC to exit without saving for settings menus
Improved RGB hinting for color submenus

"""



#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Constants: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

black = const(0)
white = const(65535)
default_ui_color = const(53243)
default_bg_color = const(4421)
default_ui_sound = const(True)
default_volume = const(2)

display_width = const(240)
display_height = const(135)

tft = None
beep = None
kb = None

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Define Settings: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

settings = [
	('volume', {'type': 'volume'}),
	('ui_color', {'type': 'color'}),
	('bg_color', {'type': 'color'}),
	('wifi_ssid', {'type': 'string'}),
	('wifi_pass', {'type': 'password'}),
	('sync_clock', {'type': 'bool'}),
	('timezone', {'type': 'int', 'min': -12, 'max': 14}), # sorry :30 timezones
	('irc_nick', {'type': 'string'}),
	('irc_server', {'type': 'string'}),
	('irc_port', {'type': 'int', 'min': 0, 'max': 65535}),
	('irc_pass', {'type': 'password'}),
	('confirm', {'type': 'confirm'})
	]

config = {
	"ui_color": default_ui_color,
	"bg_color": default_bg_color,
	"ui_sound": default_ui_sound,
	"volume": default_volume,
	"wifi_ssid": '',
	"wifi_pass": '',
	"sync_clock": True,
	"timezone": 0,
	"irc_nick": "m5user",
	"irc_server": "irc.libera.chat",
	"irc_port": 6667,
	"irc_pass": ''
}

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Function Definitions: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def play_sound(notes, time_ms, volume=config["volume"]):
	if config["ui_sound"]:
		beep.play(notes, time_ms, volume)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Setting Picker Functions: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_color(setting_name): # ~~~~~~~~~~~~~~~~~~~~~~~ get_color ~~~~~~~~~~~~~~~~~~~~~~~~~
	previous_color = config[setting_name]
	r,g,b = mh.separate_color565(previous_color)
	
	# draw pop-up menu box
	tft.fill_rect(10,10,220,115,config["bg_color"])
	tft.rect(9,9,222,117,config["ui_color"])
	tft.hline(10,126,222,black)
	tft.hline(11,127,222,black)
	tft.hline(12,128,222,black)
	tft.hline(13,129,222,black)
	tft.vline(231,10,117,black)
	tft.vline(232,11,117,black)
	tft.vline(233,12,117,black)
	tft.vline(234,13,117,black)
	
	tft.text(fontsmall, setting_name, 120 - ((len(setting_name)* 8) // 2), 20, config["ui_color"], config["bg_color"])
	tft.text(fontsmall, "R/31", 62, 40, 63488, config["bg_color"])
	tft.text(fontsmall, "G/63", 106, 40, 2016, config["bg_color"])
	tft.text(fontsmall, "B/31", 150, 40, 31, config["bg_color"])

	
	
	rgb_select_index = 0
	
	pressed_keys = []
	prev_pressed_keys = kb.get_pressed_keys()
	
	redraw = True
	
	up_hold_timer = 0
	down_hold_timer = 0
	
	while True:
		pressed_keys = kb.get_pressed_keys()
		if pressed_keys:
			if "," in pressed_keys and "," not in prev_pressed_keys: # left arrow
				rgb_select_index -= 1
				rgb_select_index %= 3
				play_sound(("C3","A3"), 80)
				redraw = True

				refresh_display = True
			elif "/" in pressed_keys and "/" not in prev_pressed_keys: # right arrow
				rgb_select_index += 1
				play_sound(("C3","A3"), 80)
				rgb_select_index %= 3
				redraw = True
			elif ";" in pressed_keys: # up arrow
				if ";" not in prev_pressed_keys: # newly pressed
					if rgb_select_index == 0:
						r += 1
						r %= 32
					elif rgb_select_index == 1:
						g += 1
						g %= 64
					elif rgb_select_index == 2:
						b += 1
						b %= 32
					play_sound("D4", 100)
					redraw = True
					up_hold_timer = 0
					
				else: # up button held
					
					up_hold_timer += 1
					if up_hold_timer > 1000:
						up_hold_timer = 800
						if rgb_select_index == 0:
							r += 1
							r %= 32
						elif rgb_select_index == 1:
							g += 1
							g %= 64
						elif rgb_select_index == 2:
							b += 1
							b %= 32
						play_sound("D4", 100)
						redraw = True
						
				
			elif "." in pressed_keys: # down arrow
				if "." not in prev_pressed_keys:
					if rgb_select_index == 0:
						r -= 1
						r %= 32
					elif rgb_select_index == 1:
						g -= 1
						g %= 64
					elif rgb_select_index == 2:
						b -= 1
						b %= 32
					play_sound("D4", 100)
					redraw = True
					down_hold_timer = 0
					
				else:
					down_hold_timer += 1
					if down_hold_timer > 1000:
						down_hold_timer = 800
						if rgb_select_index == 0:
							r -= 1
							r %= 32
						elif rgb_select_index == 1:
							g -= 1
							g %= 64
						elif rgb_select_index == 2:
							b -= 1
							b %= 32
						play_sound("D4", 100)
						redraw = True
				
				
				
			elif ("GO" in pressed_keys and "GO" not in prev_pressed_keys) or ("ENT" in pressed_keys and "ENT" not in prev_pressed_keys): # confirm settings
				play_sound(("C4","D4","E4"), 50)
				return mh.combine_color565(r,g,b)
			elif "`" in pressed_keys and "`" not in prev_pressed_keys:
				play_sound(("E4","D4","C4"), 50)
				return previous_color
			

					
		
		# graphics!
		
		if redraw:
			tft.fill_rect(62, 60, 128, 32, config["bg_color"])
			
			#draw the numbers
			for idx, clr in enumerate((r,g,b)):
				if idx == rgb_select_index:
					tft.text(font, str(clr), 62 + (44*idx), 60, white, black)
				else:
					tft.text(font, str(clr), 62 + (44*idx), 60, config["ui_color"], config["bg_color"])
			
			# pointer!
			tft.fill_rect(62, 94, 134, 24, config["bg_color"])
			for i in range(0,16):
				tft.hline(
					x = (78 - i) + (44 * rgb_select_index),
					y = 94 + i,
					length = 2 + (i*2),
					color = mh.combine_color565(r,g,b))
			tft.fill_rect(62 + (44 * rgb_select_index), 110, 34, 8, mh.combine_color565(r,g,b))

			
			
			redraw = False

		prev_pressed_keys = pressed_keys
			
			
			
			
			
def get_volume(setting_name): # ~~~~~~~~~~~~~~~~~~~~~~~ get_volume ~~~~~~~~~~~~~~~~~~~~~~~~~
	previous_value = config[setting_name]
	current_value = previous_value
	
	# draw pop-up menu box
	tft.fill_rect(10,10,220,115,config["bg_color"])
	tft.rect(9,9,222,117,config["ui_color"])
	tft.hline(10,126,222,black)
	tft.hline(11,127,222,black)
	tft.hline(12,128,222,black)
	tft.hline(13,129,222,black)
	tft.vline(231,10,117,black)
	tft.vline(232,11,117,black)
	tft.vline(233,12,117,black)
	tft.vline(234,13,117,black)
	
	# arrows
	for i in range(0,8):
		tft.hline(
			x = (119 - i),
			y = 60 + i,
			length = 2 + (i*2),
			color = config["ui_color"])
		tft.hline(
			x = (119 - i),
			y = 116 - i,
			length = 2 + (i*2),
			color = config["ui_color"])
	
	tft.text(font, setting_name, 120 - ((len(setting_name)* 16) // 2), 20, config["ui_color"], config["bg_color"])
	
	pressed_keys = []
	prev_pressed_keys = kb.get_pressed_keys()
	
	redraw = True
	
	while True:
		pressed_keys = kb.get_pressed_keys()
		if pressed_keys != prev_pressed_keys:
			if ";" in pressed_keys and ";" not in prev_pressed_keys: # up arrow
				current_value += 1
				current_value %= 11
				play_sound("D3", 140, current_value)
				redraw = True
			elif "." in pressed_keys and "." not in prev_pressed_keys: # down arrow
				current_value -= 1
				current_value %= 11
				play_sound("D3", 140, current_value)
				redraw = True
			elif ("GO" in pressed_keys and "GO" not in prev_pressed_keys) or ("ENT" in pressed_keys and "ENT" not in prev_pressed_keys): # confirm settings
				play_sound(("C4","D4","E4"), 50, current_value)
				return current_value
			elif "`" in pressed_keys and "`" not in prev_pressed_keys:
				play_sound(("E4","D4","C4"), 50)
				return previous_value
			
		# graphics!
		
		if redraw:
			tft.fill_rect(62, 75, 128, 32, config["bg_color"])
			
			tft.text(font, str(current_value), 112 - ((current_value == 10) * 8), 75, config["ui_color"], config["bg_color"])

			
			
			redraw = False

		prev_pressed_keys = pressed_keys
		
		
		
def get_text(setting_name): # ~~~~~~~~~~~~~~~~~~~~~~~ get_text ~~~~~~~~~~~~~~~~~~~~~~~~~
	previous_value = config[setting_name]
	current_value = previous_value
	
	# draw pop-up menu box
	tft.fill_rect(10,10,220,115,config["bg_color"])
	tft.rect(9,9,222,117,config["ui_color"])
	tft.hline(10,126,222,black)
	tft.hline(11,127,222,black)
	tft.hline(12,128,222,black)
	tft.hline(13,129,222,black)
	tft.vline(231,10,117,black)
	tft.vline(232,11,117,black)
	tft.vline(233,12,117,black)
	tft.vline(234,13,117,black)
	
	# arrows
	
	tft.text(font, setting_name, 120 - ((len(setting_name)* 16) // 2), 20, config["ui_color"], config["bg_color"])
	
	pressed_keys = []
	prev_pressed_keys = kb.get_pressed_keys()
	
	redraw = True
	
	while True:
		pressed_keys = kb.get_pressed_keys()
		if pressed_keys != prev_pressed_keys:
			if ("GO" in pressed_keys and "GO" not in prev_pressed_keys) or ("ENT" in pressed_keys and "ENT" not in prev_pressed_keys): # confirm settings
				play_sound(("C4","D4","E4"), 50)
				return current_value
			
			elif 'BSPC' in pressed_keys and 'BSPC' not in prev_pressed_keys:
				current_value = current_value[0:-1]
				redraw = True
			elif 'SPC' in pressed_keys and 'SPC' not in prev_pressed_keys:
				current_value = current_value + ' '
				redraw = True
			elif "ESC" in pressed_keys and "ESC" not in prev_pressed_keys:
				play_sound(("E4","D4","C4"), 50)
				return previous_value
			else:
				for key in pressed_keys:
					if len(key) == 1 and key not in prev_pressed_keys:
						current_value += key
					redraw = True
		
		# graphics!
		if redraw:
			tft.fill_rect(12, 59, 216, 64, config["bg_color"])
			if len(current_value) <= 12:
				tft.text(font, current_value, 120 - (len(current_value) * 8), 75, config["ui_color"], config["bg_color"])
			else:
				tft.text(font, current_value[0:12], 24, 59, config["ui_color"], config["bg_color"])
				tft.text(font, current_value[12:], 120 - (len(current_value[12:]) * 8), 91, config["ui_color"], config["bg_color"])

			
			
			redraw = False

		prev_pressed_keys = pressed_keys
		
		
		
		
		
			
def get_bool(setting_name): # ~~~~~~~~~~~~~~~~~~~~~~~ get_bool ~~~~~~~~~~~~~~~~~~~~~~~~~
	previous_value = config[setting_name]
	current_value = previous_value
	
	# draw pop-up menu box
	tft.fill_rect(10,10,220,115,config["bg_color"])
	tft.rect(9,9,222,117,config["ui_color"])
	tft.hline(10,126,222,black)
	tft.hline(11,127,222,black)
	tft.hline(12,128,222,black)
	tft.hline(13,129,222,black)
	tft.vline(231,10,117,black)
	tft.vline(232,11,117,black)
	tft.vline(233,12,117,black)
	tft.vline(234,13,117,black)
	
	# arrows
	for i in range(0,8):
		tft.hline(
			x = (119 - i),
			y = 60 + i,
			length = 2 + (i*2),
			color = config["ui_color"])
		tft.hline(
			x = (119 - i),
			y = 116 - i,
			length = 2 + (i*2),
			color = config["ui_color"])
	
	tft.text(font, setting_name, 120 - ((len(setting_name)* 16) // 2), 20, config["ui_color"], config["bg_color"])
	
	pressed_keys = []
	prev_pressed_keys = kb.get_pressed_keys()
	
	redraw = True
	
	while True:
		pressed_keys = kb.get_pressed_keys()
		if pressed_keys != prev_pressed_keys:
			if ";" in pressed_keys and ";" not in prev_pressed_keys: # up arrow
				current_value = not current_value
				play_sound("D3", 140)
				redraw = True
			elif "." in pressed_keys and "." not in prev_pressed_keys: # down arrow
				current_value = not current_value
				play_sound("D3", 140)
				redraw = True
			elif ("GO" in pressed_keys and "GO" not in prev_pressed_keys) or ("ENT" in pressed_keys and "ENT" not in prev_pressed_keys): # confirm settings
				play_sound(("C4","D4","E4"), 50)
				return current_value
			elif "`" in pressed_keys and "`" not in prev_pressed_keys:
				play_sound(("E4","D4","C4"), 50)
				return previous_value
			
		# graphics!
		if redraw:
			tft.fill_rect(62, 75, 128, 32, config["bg_color"])
			if current_value:
				tft.text(font, 'ON', 104, 75, config["ui_color"], config["bg_color"])
			else:
				tft.text(font, 'OFF', 96, 75, config["ui_color"], config["bg_color"])

			redraw = False

		prev_pressed_keys = pressed_keys
		

def get_int(setting_name, minimum, maximum): # ~~~~~~~~~~~~~~~~~~~~~~~ get_int ~~~~~~~~~~~~~~~~~~~~~~~~~
	previous_value = config[setting_name]
	current_value = previous_value
	
	# draw pop-up menu box
	tft.fill_rect(10,10,220,115,config["bg_color"])
	tft.rect(9,9,222,117,config["ui_color"])
	tft.hline(10,126,222,black)
	tft.hline(11,127,222,black)
	tft.hline(12,128,222,black)
	tft.hline(13,129,222,black)
	tft.vline(231,10,117,black)
	tft.vline(232,11,117,black)
	tft.vline(233,12,117,black)
	tft.vline(234,13,117,black)
	
	# arrows
	for i in range(0,8):
		tft.hline(
			x = (119 - i),
			y = 60 + i,
			length = 2 + (i*2),
			color = config["ui_color"])
		tft.hline(
			x = (119 - i),
			y = 116 - i,
			length = 2 + (i*2),
			color = config["ui_color"])
	
	tft.text(font, setting_name, 120 - ((len(setting_name)* 16) // 2), 20, config["ui_color"], config["bg_color"])
	
	pressed_keys = []
	prev_pressed_keys = kb.get_pressed_keys()
	
	redraw = True
	
	while True:
		pressed_keys = kb.get_pressed_keys()
		if pressed_keys != prev_pressed_keys:
			if ";" in pressed_keys and ";" not in prev_pressed_keys: # up arrow
				current_value += 1
				if current_value > maximum:
					current_value = minimum
				play_sound("D3", 140)
				redraw = True
			elif "." in pressed_keys and "." not in prev_pressed_keys: # down arrow
				current_value -= 1
				if current_value < minimum:
					current_value = maximum
				play_sound("D3", 140)
				redraw = True
			elif ("GO" in pressed_keys and "GO" not in prev_pressed_keys) or ("ENT" in pressed_keys and "ENT" not in prev_pressed_keys): # confirm settings
				play_sound(("C4","D4","E4"), 50)
				return current_value
			elif "`" in pressed_keys and "`" not in prev_pressed_keys:
				play_sound(("E4","D4","C4"), 50)
				return previous_value
				
		# graphics!
		if redraw:
			tft.fill_rect(62, 75, 128, 32, config["bg_color"])
			tft.text(font, str(current_value), 120 - (len(str(current_value)) * 8), 75, config["ui_color"], config["bg_color"])

			redraw = False

		prev_pressed_keys = pressed_keys
		









#--------------------------------------------------------------------------------------------------
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main Loop: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#--------------------------------------------------------------------------------------------------




def main_loop():
	global config, tft, kb, beep
	#bump up our clock speed so the UI feels smoother (240mhz is the max officially supported, but the default is 160mhz)
	machine.freq(240_000_000)
	
	#init the keyboard
	kb = keyboard.KeyBoard()
	pressed_keys = []
	prev_pressed_keys = []
	
	
	
	
	#init driver for the graphics
	spi = SPI(1, baudrate=40000000, sck=Pin(36), mosi=Pin(35), miso=None)
	tft = st7789.ST7789(
	spi,
	display_height,
	display_width,
	reset=Pin(33, Pin.OUT),
	cs=Pin(37, Pin.OUT),
	dc=Pin(34, Pin.OUT),
	backlight=Pin(38, Pin.OUT),
	rotation=1,
	color_order=st7789.BGR
	)
	
	
	
	
	# variables:

	#load config
	try:
		with open("config.json", "r") as conf:
			config_overlay = json.loads(conf.read())
			for key in config_overlay:
				config[key] = config_overlay[key]
	except:
		print("could not load settings from config.json. reloading default values.")
		config_modified = True
		with open("config.json", "w") as conf:
			conf.write(json.dumps(config))
	
	force_redraw_display = True
	refresh_display = True
	
	mid_color = mh.mix_color565(config["ui_color"], config["bg_color"])
	
	cursor_index = 0
	prev_cursor_index = 0
	setting_screen_index = 0
	
	
	#init the beeper!
	beep = beeper.Beeper()
	
	#init diplsay
	tft.fill_rect(0,0,display_width, display_height, config["bg_color"])
	
	
	while True:
		
		
		# ----------------------- check for key presses on the keyboard. Only if they weren't already pressed. --------------------------
		pressed_keys = kb.get_pressed_keys()
		if pressed_keys != prev_pressed_keys:
			# ~~~~~~ check if the arrow keys are newly pressed ~~~~~
			if ";" in pressed_keys and ";" not in prev_pressed_keys: # up arrow
				cursor_index -= 1
				play_sound(("E3","C3"), 100)
				if cursor_index < 0:
					cursor_index = len(settings) - 1
				refresh_display = True
			elif "." in pressed_keys and "." not in prev_pressed_keys: # down arrow
				cursor_index += 1
				play_sound(("D3","C3"), 100)
				if cursor_index >= len(settings):
					cursor_index = 0
				refresh_display = True
			
			if "GO" in pressed_keys or "ENT" in pressed_keys:
				# SETTINGS EDIT
				
				setting_name, setting_type = settings[cursor_index]

				if setting_type["type"] == "int":
					value = get_int(setting_name, setting_type["min"], setting_type["max"])
					config[setting_name] = value
				elif setting_type["type"] == "color":
					color = get_color(setting_name)
					config[setting_name] = color
					mid_color = mh.mix_color565(config["ui_color"], config["bg_color"])
				elif setting_type["type"] == "volume":
					value = get_volume(setting_name)
					config[setting_name] = value
				elif setting_type["type"] == "string" or setting_type["type"] == "password":
					text = get_text(setting_name)
					config[setting_name] = text
				elif setting_type["type"] == "bool":
					value = get_bool(setting_name)
					config["sync_clock"] = value
				elif setting_type["type"] == 'confirm': 
					with open("config.json", "w") as conf: #save changes
						conf.write(json.dumps(config))
					play_sound(("C4","D4",("C3","E3","D3")), 100)
					del beep
					# shut off the display
					tft.fill(black)
					tft.sleep_mode(True)
					Pin(38, Pin.OUT).value(0) #backlight off
					spi.deinit()
					# return home
					machine.freq(160_000_000)
					time.sleep_ms(10)
					machine.reset()

				force_redraw_display = True
				pressed_keys = kb.get_pressed_keys()

			elif "`" in pressed_keys and "`" not in prev_pressed_keys:
					play_sound((("C3","E3","D3"),"D4","C4"), 100)
					del beep
					# shut off the display
					tft.fill(black)
					tft.sleep_mode(True)
					Pin(38, Pin.OUT).value(0) #backlight off
					spi.deinit()
					# return home
					machine.freq(160_000_000)
					time.sleep_ms(10)
					machine.reset()
					
					
			# once we parse the keypresses for this loop, we need to store them for next loop
			prev_pressed_keys = pressed_keys
			
		#scroll up and down logic
		if cursor_index >= setting_screen_index + 4:
			setting_screen_index += cursor_index - (setting_screen_index + 3)
			force_redraw_display = True
		elif cursor_index < setting_screen_index:
			#setting_screen_index -= 1
			setting_screen_index -= setting_screen_index - cursor_index
			force_redraw_display = True
			
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main Graphics: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		
		
		#write out all text
		if refresh_display or force_redraw_display:
			
			#blackout previous text
			if not force_redraw_display:
				tft.fill_rect(x=0, y=(32 * (prev_cursor_index - setting_screen_index)) + 4, width=238, height=32, color=config["bg_color"])
			
			# draw text
			for i in range(setting_screen_index, setting_screen_index + 4):
				
				#blackout previous text 
				if force_redraw_display:
					tft.fill_rect(0,4 + ((i - setting_screen_index) * 32),238,32,config["bg_color"])
					
					#scroll bar
					max_screen_index = len(settings) - 4
					scrollbar_height = 135 // max_screen_index
					scrollbar_position = math.floor((135 - scrollbar_height) * (setting_screen_index / max_screen_index))
					
					tft.fill_rect(238, 0, 2, 135, config["bg_color"])
					tft.fill_rect(238, scrollbar_position, 2, scrollbar_height, mid_color)
					
				setting_name, setting_type = settings[i]
				if setting_name != 'confirm' and setting_type["type"] != 'password':
					# display value:
					tft.text(fontsmall,
								 str(config[setting_name]),
								 ((240 - (8 * len( str(config[setting_name]) ))) + (16 * len(setting_name) ) ) // 2, # centered in the empty space
								 (32 * (i - setting_screen_index)) + 18,
								 mid_color,config["bg_color"])
				
				#custom style for the confirm button
				if setting_name == "confirm":
					if cursor_index == i: # the currently selected text
						tft.text(font,"< Confirm >",32, (32 * (i - setting_screen_index)) + 4,white,mid_color)
						
					elif prev_cursor_index == i or force_redraw_display: # unselected text
						tft.text(font,"Confirm",64, (32 * (i - setting_screen_index)) + 4,config["ui_color"],config["bg_color"])
						
				else:
					if cursor_index == i: # the currently selected text
						tft.text(font,'>' + setting_name + '',-2, (32 * (i - setting_screen_index)) + 4,white,mid_color)
						
					elif prev_cursor_index == i or force_redraw_display: # unselected text
						tft.text(font,setting_name,6, (32 * (i - setting_screen_index)) + 4,config["ui_color"],config["bg_color"])
			
			#dividing lines
			tft.hline(0,36,234,mid_color)
			tft.hline(0,68,234,mid_color)
			tft.hline(0,100,234,mid_color)
			
			

			refresh_display = False 
			

			
		#update prev app selector index to current one for next cycle
		prev_cursor_index = cursor_index
		force_redraw_display = False
		
# run the main loop!
main_loop()





