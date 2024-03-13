import network
from lib import beeper

# wifi and beeper consume most memory
nic = network.WLAN(network.STA_IF)
beep = beeper.Beeper()

import gc
gc.collect()

from font import vga1_8x16 as fontsmall
from font import vga2_16x32 as font
from machine import Pin, SDCard, SPI, ADC, RTC, reset
import time, os, json, math, ntptime
from lib import keyboard, beeper, battlevel
from lib import microhydra as mh
from lib.mhconfig import Config
gc.collect()
from lib import st7789py as st7789
from launcher.icons import icons, battery


"""

VERSION: 0.8

CHANGES:
	Created mhconfig.Config, mhoverlay.UI_Overlay, cleaned up launcher.py, endured the horrors
	Renamed constants to make them "real" constants, and added slight improvements to st7789fbuf.py
	
This program is designed to be used in conjunction with "main.py" apploader, to select and launch MPy apps.

The basic app loading logic works like this:
 - apploader reads reset cause and RTC.memory to determine which app to launch
 - apploader launches 'launcher.py' when hard reset, or when RTC.memory is blank
 - launcher scans app directories on flash and SDCard to find apps
 - launcher shows list of apps, allows user to select one
 - launcher stores path to app in RTC.memory, and soft-resets the device
 - apploader reads RTC.memory to find path of app to load
 - apploader clears the RTC.memory, and imports app at the given path
 - app at given path now has control of device.
 - pressing the reset button will relaunch the launcher program, and so will calling machine.reset() from the app. 

This approach was chosen to reduce the chance of conflicts or memory errors when switching apps.
Because MicroPython completely resets between apps, the only "wasted" ram from the app switching process will be from main.py

"""

#init beeper asap to help prevent volume bug
beep = beeper.Beeper()
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Constants: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

_TARGET_VSCSAD = const(40) # scrolling display "center"

_DISPLAY_WIDTH = const(240)
_DISPLAY_WIDTH_HALF = const(120)
_DISPLAY_HEIGHT = const(135)
_DISPLAY_OFFBOUND = const(40)

_MAX_WIFI_ATTEMPTS = const(1000)
_MAX_NTP_ATTEMPTS = const(10)

_WIDGET_BATTERY_X = const(212)
_WIDGET_BATTERY_Y = const(4)
_WIDGET_BATTERY_W = const(20)
_WIDGET_BATTERY_H = const(10)
_WIDGET_SCROLL_Y = const(133)
_WIDGET_SCROLL_H = const(2)
_WIDGET_CLOCK_X = const(6)
_WIDGET_CLOCK_Y = const(2)
_WIDGET_CLOCK_W = const(58)
_WIDGET_CLOCK_H = const(16)

_UI_STATUS_H = const(18)
_UI_ICON_X = const(104)
_UI_ICON_Y = const(36)
_UI_APP_H = const(32 + 34 + 10)
_UI_APP_CLEAR_W = const(200)
_UI_APP_CLEAR_X = const(20)#display_width_half - _UI_APP_CLEAR_W / 2
_UI_APPNAME_Y = const(80)

special_apps = {
	"ui_sound": "UI Sound",
	"reload_apps": "Reload Apps",
	"settings": "Settings"
}

toggle_labels = [
	"Off",
	"On"
]

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Globals: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

config = None

widget_scroll_w = _DISPLAY_WIDTH

battery_widget = []

tft = None
rtc = RTC()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Finding Apps ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~




def scan_apps(sd):
	global widget_scroll_w
	# first we need a list of apps located on the flash or SDCard

	main_directory = os.listdir("/")
	
	
	# if the sd card is not mounted, we need to mount it.
	if "sd" not in main_directory:
		try:
			sd = SDCard(slot=2, sck=Pin(40), miso=Pin(39), mosi=Pin(14), cs=Pin(12))
		except OSError as e:
			print(e)
			print("SDCard couldn't be initialized. This might be because it was already initialized and not properly deinitialized.")
			try:
				sd.deinit()
			except:
				print("Couldn't deinitialize SDCard")
				
		try:
			os.mount(sd, '/sd')
		except OSError as e:
			print(e)
			print("Could not mount SDCard.")
		except NameError as e:
			print(e)
			print("SDCard not mounted")
			
		main_directory = os.listdir("/")

	sd_directory = []
	if "sd" in main_directory:
		sd_directory = os.listdir("/sd")

	# if the apps folder does not exist, create it.
	if "apps" not in main_directory:
		os.mkdir("/apps")
		main_directory = os.listdir("/")
		
	# do the same for the sdcard apps directory
	if "apps" not in sd_directory and "sd" in main_directory:
		os.mkdir("/sd/apps")
		sd_directory = os.listdir("/sd")



	# if everything above worked, sdcard should be mounted (if available), and both app directories should exist. now look inside to find our apps:
	main_app_list = os.listdir("/apps")
	sd_app_list = []

	if "sd" in main_directory:
		try:
			sd_app_list = os.listdir("/sd/apps")
		except OSError as e:
			print(e)
			print("SDCard mounted but cant be opened; assuming it's been removed. Unmounting /sd.")
			os.umount('/sd')




	# now lets collect some separate app names and locations
	app_names = []
	app_paths = {}

	for entry in main_app_list:
		if entry.endswith(".py"):
			this_name = entry[:-3]
			
			# the purpose of this check is to prevent dealing with duplicated apps.
			# if multiple apps share the same name, then we will simply use the app found most recently. 
			if this_name not in app_names:
				app_names.append( this_name ) # for pretty display
			
			app_paths[f"{this_name}"] = f"/apps/{entry}"

		elif entry.endswith(".mpy"):
			this_name = entry[:-4]
			if this_name not in app_names:
				app_names.append( this_name )
			app_paths[f"{this_name}"] = f"/apps/{entry}"
			
			
	for entry in sd_app_list:
		if entry.endswith(".py"): #repeat for sdcard
			this_name = entry[:-3]
			
			if this_name not in app_names:
				app_names.append( this_name )
			
			app_paths[f"{this_name}"] = f"/sd/apps/{entry}"
			
		elif entry.endswith(".mpy"):
			this_name = entry[:-4]
			if this_name not in app_names:
				app_names.append( this_name )
			app_paths[f"{this_name}"] = f"/sd/apps/{entry}"
			
	#sort alphabetically without uppercase/lowercase discrimination:
	app_names.sort(key=lambda element: element.lower())
	
	#add an appname to refresh the app list
	app_names.append(special_apps["reload_apps"])
	#add an appname to control the beeps
	app_names.append(special_apps["ui_sound"])
	#add an appname to open settings app
	app_names.append(special_apps["settings"])
	app_paths[special_apps["settings"]] = "/launcher/settings.py"
	
	widget_scroll_w = _DISPLAY_WIDTH // len(app_names)
	
	return app_names, app_paths, sd

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Function Definitions: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def launch_app(app_path):
	#print(f'launching {app_path}')
	rtc.memory(app_path)
	print(f"Launching '{app_path}...'")
	# reset clock speed to default. 
	#machine.freq(160_000_000)
	time.sleep_ms(50)
	reset()
	



def center_text_x(text, char_width = 16):
	"""
		Calculate the x coordinate to draw a text string, to make it horizontally centered. (plus the text width)
	"""
	str_width = len(text) * char_width
	# display is 240 px wide
	start_coord = _DISPLAY_WIDTH_HALF - (str_width // 2)
	
	return start_coord, str_width


def ease_in_cubic(x):
	return x * x * x

def ease_out_cubic(x):
	return 1 - ((1 - x) ** 3)
		
		

def time_24_to_12(hour_24,minute):
	ampm = 'am'
	if hour_24 >= 12:
		ampm = 'pm'
		
	hour_12 = hour_24 % 12
	if hour_12 == 0:
		hour_12 = 12
		
	time_string = f"{hour_12}:{'{:02d}'.format(minute)}"
	return time_string, ampm


def erase_widgets():
	tft.fill_rect(0, _WIDGET_SCROLL_Y, _DISPLAY_WIDTH, _WIDGET_SCROLL_H, config["bg_color"]) # erase scrollbar
	#tft.fill_rect(_WIDGET_CLOCK_X + offset, _WIDGET_CLOCK_Y, _WIDGET_CLOCK_W, _WIDGET_CLOCK_H, config.palette[2]) # erase clock
	#tft.fill_rect(_WIDGET_BATTERY_X + offset, _WIDGET_BATTERY_Y, _WIDGET_BATTERY_W, _WIDGET_BATTERY_H, config.palette[2]) # erase battery
	tft.fill_rect(0, 0, _DISPLAY_WIDTH, _UI_STATUS_H, config.palette[2])

def draw_widgets(offset, app_selector_index, battlevel):
	#scroll bar
	tft.fill_rect((widget_scroll_w * app_selector_index) + offset, 133, widget_scroll_w, _WIDGET_SCROLL_H, config.palette[2])
	
	#clock
	_,_,_, hour_24, minute, _,_,_ = time.localtime()
	formatted_time, ampm = time_24_to_12(hour_24, minute)
	tft.text(fontsmall, formatted_time, _WIDGET_CLOCK_X + offset, _WIDGET_CLOCK_Y, config["ui_color"], config.palette[2])
	tft.text(fontsmall, ampm, _WIDGET_CLOCK_X + 2 + (len(formatted_time) * 8) + offset, _WIDGET_CLOCK_Y, config["bg_color"], config.palette[2])
	
	#battery
	tft.bitmap_icons(battery, battery_widget[battlevel]["icon"], (config.palette[2],battery_widget[battlevel]["color"]), _WIDGET_BATTERY_X + offset, _WIDGET_BATTERY_Y)

def play_sound(notes, time_ms):
	if config["ui_sound"]:
		beep.play(notes, time_ms, config["volume"])

def draw_app(offset, text, icon, label=None):
	tft.fill_rect(_UI_APP_CLEAR_X + offset, _UI_ICON_Y, _UI_APP_CLEAR_W, _UI_APP_H, config["bg_color"])

	tft.text(font, text, center_text_x(text)[0] + offset, _UI_APPNAME_Y, config["ui_color"], config["bg_color"])
	if label:
		tft.text(font, label, center_text_x(label)[0] + offset, _UI_ICON_Y, config["ui_color"], config["bg_color"])
	else:
		tft.bitmap_icons(icons, icon, (config["bg_color"], config["ui_color"]), _UI_ICON_X + offset, _UI_ICON_Y)

#--------------------------------------------------------------------------------------------------
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main Loop: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#--------------------------------------------------------------------------------------------------




def main_loop():
	global config
	global widget_scroll_w
	global battery_widget
	global tft, beep, nic

	#bump up our clock speed so the UI feels smoother (240mhz is the max officially supported, but the default is 160mhz)
	#machine.freq(240_000_000)
	
	
	# load our config asap to support other processes
	config = Config()

	battery_widget = [
		{"icon": battery.EMPTY, "color": config.rgb_colors[0]},
		{"icon": battery.LOW, "color": config["ui_color"]},
		{"icon": battery.HIGH, "color": config["ui_color"]},
		{"icon": battery.FULL, "color": config.rgb_colors[1]}
	]
		
	# sync our RTC on boot, if set in settings
	syncing_clock = config["sync_clock"]
	sync_ntp_attemps = 0
	connect_wifi_attemps = 0
	
	#wifi loves to give unknown runtime errors, just try it twice:
	if not nic:
		try:
			nic = network.WLAN(network.STA_IF)
		except RuntimeError as e:
			print(e)
			try:
				nic = network.WLAN(network.STA_IF)
			except RuntimeError as e:
				print("Wifi WLAN object couldnt be created. Gave this error:",e)
				import micropython
				print(micropython.mem_info(),micropython.qstr_info())
		
	if config["wifi_ssid"] == '':
		syncing_clock = False # no point in wasting resources if wifi hasn't been setup
	elif rtc.datetime()[0] != 2000: #clock wasn't reset, assume that time has already been set
		syncing_clock = False
		
	if syncing_clock: #enable wifi if we are syncing the clock
		if not nic.active(): # turn on wifi if it isn't already
			nic.active(True)
		if not nic.isconnected(): # try connecting
			try:
				nic.connect(config["wifi_ssid"], config["wifi_pass"])
			except OSError as e:
				print("wifi_sync_rtc had this error when connecting:",e)
	
	#before anything else, we should scan for apps
	sd = None #dummy var for when we cant mount SDCard
	app_names, app_paths, sd = scan_apps(sd)
	app_selector_index = 0
	prev_selector_index = 0
	
	
	#init the keyboard
	kb = keyboard.KeyBoard()
	pressed_keys = []
	prev_pressed_keys = []
	
	#init the ADC for the battery
	batt = battlevel.Battery()
	
	#init driver for the graphics
	spi = SPI(1, baudrate=40000000, sck=Pin(36), mosi=Pin(35), miso=None)
	tft = st7789.ST7789(
		spi,
		_DISPLAY_HEIGHT,
		_DISPLAY_WIDTH,
		reset=Pin(33, Pin.OUT),
		cs=Pin(37, Pin.OUT),
		dc=Pin(34, Pin.OUT),
		backlight=Pin(38, Pin.OUT),
		rotation=1,
		color_order=st7789.BGR)
	
	tft.vscrdef(_DISPLAY_OFFBOUND, _DISPLAY_WIDTH, _DISPLAY_OFFBOUND)
	tft.vscsad(_TARGET_VSCSAD)
	
	nonscroll_elements_displayed = False
	
	force_redraw_display = True
	
	#this is used as a flag to tell a future loop to redraw the frame mid-scroll animation
	delayed_redraw = False
	
	launching = False
	current_vscsad = _TARGET_VSCSAD
	prev_vscsad = _TARGET_VSCSAD
	
	scroll_direction = 0 #1 for right, -1 for left, 0 for center
	refresh_timer = 0
	
	#starupp sound
	play_sound(('C3',
		('F3'),
		('A3'),
		('F3','A3','C3'),
		('F3','A3','C3')),130)
		
		
	#init diplsay
	tft.fill_rect(-_DISPLAY_OFFBOUND, 0, _DISPLAY_WIDTH + _DISPLAY_OFFBOUND, _DISPLAY_HEIGHT, config["bg_color"])
	tft.fill_rect(-_DISPLAY_OFFBOUND, 0, _DISPLAY_WIDTH + _DISPLAY_OFFBOUND, _UI_STATUS_H, config.palette[2])
	tft.hline(-_DISPLAY_OFFBOUND, _UI_STATUS_H, _DISPLAY_WIDTH + _DISPLAY_OFFBOUND, config.palette[0])
	
	while True:
		
		
		# ----------------------- check for key presses on the keyboard. Only if they weren't already pressed. --------------------------
		new_keys = kb.get_new_keys()
		if new_keys:
			
			# ~~~~~~ check if the arrow keys are newly pressed ~~~~~
			if "/" in new_keys: # right arrow
				app_selector_index += 1
				
				#animation:

				scroll_direction = 1
				current_vscsad = _TARGET_VSCSAD
				play_sound((("C5","D4"),"A4"), 80)

				
			elif "," in new_keys: # left arrow
				app_selector_index -= 1
				
				#animation:
				
				scroll_direction = -1
				
				#this prevents multiple scrolls from messing up the animation
				current_vscsad = _TARGET_VSCSAD
				
				play_sound((("B3","C5"),"A4"), 80)
				
			
		
			# ~~~~~~~~~~ check if GO or ENTER are pressed ~~~~~~~~~~
			if "GO" in new_keys:
				
				# special "settings" app options will have their own behaviour, otherwise launch the app
				if app_names[app_selector_index] == special_apps["ui_sound"]:
					
					if config["ui_sound"]: # currently unmuted, then mute
						config["ui_sound"] = False
						force_redraw_display = True
						config_modified = True
					else: # currently muted, then unmute
						config["ui_sound"] = True
						force_redraw_display = True
						play_sound(("C4","G4","G4"), 100)
						config_modified = True
				
				elif app_names[app_selector_index] == special_apps["reload_apps"]:
					app_names, app_paths, sd = scan_apps(sd)
					app_selector_index = 0
					current_vscsad = _TARGET_VSCSAD + 2 # forces scroll animation triggers
					play_sound(('F3','A3','C3'),100)
						
				else: # ~~~~~~~~~~~~~~~~~~~ LAUNCH THE APP! ~~~~~~~~~~~~~~~~~~~~
					
					#save config if it has been changed:
					config.save()
						
					# shut off the display
					tft.fill(st7789.BLACK)
					tft.sleep_mode(True)
					Pin(38, Pin.OUT).value(0) #backlight off
					spi.deinit()
					
					if sd != None:
						try:
							sd.deinit()
						except:
							print("Tried to deinit SDCard, but failed.")
							
					play_sound(('C4','B4','C5','C5'),100)
						
					launch_app(app_paths[app_names[app_selector_index]])

			else: # keyboard shortcuts!
				for key in new_keys:
					# jump to letter:
					if len(key) == 1: # filter special keys
						if key in 'abcdefghijklmnopqrstuvwxyz1234567890':
							#search for that letter in the app list
							for idx, name in enumerate(app_names):
								if name.lower().startswith(key):
									#animation:
									if app_selector_index > idx:
										scroll_direction = -1
									elif app_selector_index < idx:
										scroll_direction = 1
									current_vscsad = _TARGET_VSCSAD
									# go there!
									app_selector_index = idx
									play_sound(("G3"), 100)
									found_key = True
									break
				
	
		#wrap around our selector index, in case we go over or under the target amount
		app_selector_index = app_selector_index % len(app_names)
	
	
		time.sleep_ms(4) #this loop runs about 3000 times a second without sleeps. The sleeps actually help things feel smoother.
		
		
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main Graphics: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

		#decide now if we will be redrawing the text.
		# we are capturing this so that we can black out and redraw the screen in two parts
		if (app_selector_index != prev_selector_index):
			delayed_redraw = True
		
		prev_app_text = app_names[prev_selector_index]
		current_app_text = app_names[app_selector_index]
		battlevel = batt.read_level()
				
		# if scrolling animation, move in the direction specified!
		if scroll_direction != 0:
			#erase_widgets()
			#draw_widgets(current_vscsad - _TARGET_VSCSAD, app_selector_index, battlevel)
			tft.vscsad(current_vscsad % _DISPLAY_WIDTH)
			#draw_app(current_vscsad - _TARGET_VSCSAD, current_app_text, icon, label)
			if scroll_direction == 1:
				current_vscsad += math.floor(ease_out_cubic((current_vscsad - _TARGET_VSCSAD) / _DISPLAY_WIDTH_HALF) * 20) + 5
				if current_vscsad >= 160:
					current_vscsad = -80
					scroll_direction = 0
					force_redraw_display = True
			else:
				current_vscsad -= math.floor(ease_out_cubic((current_vscsad - _TARGET_VSCSAD) / -_DISPLAY_WIDTH_HALF) * 20) + 5
				if current_vscsad <= -80:
					current_vscsad = 160
					scroll_direction = 0
					force_redraw_display = True

				
		# if vscsad/scrolling is not centered, move it toward center!
		if scroll_direction == 0 and current_vscsad != _TARGET_VSCSAD:
			#erase_widgets()
			#draw_widgets(current_vscsad - _TARGET_VSCSAD, app_selector_index, battlevel)
			tft.vscsad(current_vscsad % _DISPLAY_WIDTH)
			#draw_app(current_vscsad - _TARGET_VSCSAD, current_app_text, icon, label)
			if current_vscsad < _TARGET_VSCSAD:
				current_vscsad += (abs(current_vscsad - _TARGET_VSCSAD) // 8) + 1
			elif current_vscsad > _TARGET_VSCSAD:
				current_vscsad -= (abs(current_vscsad - _TARGET_VSCSAD) // 8) + 1

		
		# if we are scrolling, we should change some UI elements until we finish
		if nonscroll_elements_displayed and (current_vscsad != _TARGET_VSCSAD):
			erase_widgets()
			nonscroll_elements_displayed = False
			
			
		elif nonscroll_elements_displayed == False and (current_vscsad == _TARGET_VSCSAD):
		#	battlevel = read_battery_level(batt)
			draw_widgets(0, app_selector_index, battlevel)
			nonscroll_elements_displayed = True
			
		
		#refresh the text mid-scroll, or when forced
		if (delayed_redraw and scroll_direction == 0 ) or force_redraw_display:
			#delayed_redraw = False
			refresh_timer += 1

			#if force_redraw_display:
			#	erase_widgets()
			#	draw_widgets(0, app_selector_index, battlevel)
			
			#crop text for display
			if len(prev_app_text) > 15:
				prev_app_text = prev_app_text[:12] + "..."
			if len(current_app_text) > 15:
				current_app_text = current_app_text[:12] + "..."

			if refresh_timer == 2 or force_redraw_display: # redraw icon
				refresh_timer = 0
				delayed_redraw = False

				#special menu options for settings
				icon = None
				label = None
				if current_app_text == special_apps["ui_sound"]:
					label = toggle_labels[1 if config["ui_sound"] else 0]
				elif current_app_text == special_apps["reload_apps"]:
					icon = icons.RELOAD
				elif current_app_text == special_apps["settings"]:
					icon = icons.GEAR
				elif app_paths[app_names[app_selector_index]][:3] == "/sd":
					icon = icons.SDCARD
				else:
					icon = icons.FLASH
				draw_app(0, current_app_text, icon, label)
			

		
			
		
		#reset vars for next loop
		force_redraw_display = False
		prev_vscsad = current_vscsad
		
		#update prev app selector index to current one for next cycle
		prev_selector_index = app_selector_index
			
		#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ WIFI and RTC: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		
		if syncing_clock:
			if nic.isconnected():
				try:
					ntptime.settime()
				except OSError:
					sync_ntp_attemps += 1
					
				if rtc.datetime()[0] != 2000:
					nic.disconnect()
					nic.active(False) #shut off wifi
					syncing_clock = False
					#apply our timezone offset
					time_list = list(rtc.datetime())
					time_list[4] = time_list[4] + config["timezone"]
					rtc.datetime(tuple(time_list))
					print(f'RTC successfully synced to {rtc.datetime()} with {sync_ntp_attemps} attemps.')
					
				elif sync_ntp_attemps >= _MAX_NTP_ATTEMPTS:
					nic.disconnect()
					nic.active(False) #shut off wifi
					syncing_clock = False
					print(f"Syncing RTC aborted after {sync_ntp_attemps} attemps")
				
			elif connect_wifi_attemps >= _MAX_WIFI_ATTEMPTS:
				nic.disconnect()
				nic.active(False) #shut off wifi
				syncing_clock = False
				print(f"Connecting to wifi aborted after {connect_wifi_attemps} loops")
			else:
				connect_wifi_attemps += 1
		
# run the main loop!
main_loop()




