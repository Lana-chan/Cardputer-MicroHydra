from machine import Pin, SDCard, SPI, RTC, ADC
import time, os, json, math, ntptime, network
from lib import keyboard, beeper
from lib import microhydra as mh
import machine
from lib import st7789py as st7789
from launcher.icons import icons, battery
from font import vga1_8x16 as fontsmall
from font import vga2_16x32 as font





"""

VERSION: 0.7

CHANGES:
	Adjusted battery level detection, improved launcher sort method,
	added apps folders to import path,
	added ability to jump to alphabetical location in apps list,
	added new fbuf-based display driver to lib

This program is designed to be used in conjunction with the "apploader.py" program, to select and launch MPy apps for the Cardputer.

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
Because MicroPython completely resets between apps, the only "wasted" ram from the app switching process will be from launcher.py



"""



#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Constants: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

black = const(0)
white = const(65535)
default_ui_color = const(53243)
default_bg_color = const(4421)
default_ui_sound = const(True)
default_volume = const(2)

appname_y = const(80) 
target_vscsad = const(40) # scrolling display "center"

display_width = const(240)
display_width_half = const(120)
display_height = const(135)

max_wifi_attemps = const(1000)
max_ntp_attemps = const(10)

widget_battery_x = const(212)
widget_battery_y = const(4)
widget_battery_w = const(20)
widget_battery_h = const(10)
widget_scroll_y = const(133)
widget_scroll_h = const(2)
widget_clock_x = const(6)
widget_clock_y = const(2)
widget_clock_w = const(58)
widget_clock_h = const(16)

ui_icon_x = const(104)
ui_icon_y = const(36)

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

config = {
	"ui_color": default_ui_color,
	"bg_color": default_bg_color,
	"ui_sound": default_ui_sound,
	"volume": default_volume,
	"wifi_ssid": '',
	"wifi_pass": '',
	"sync_clock": True,
	"timezone": 0
}


mid_color = mh.mix_color565(config["bg_color"], config["ui_color"])
red_color = mh.color565_shiftred(config["ui_color"])
green_color = mh.color565_shiftgreen(config["ui_color"], 0.4)

widget_scroll_w = display_width

battery_widget = [
	{"icon": battery.EMPTY, "color": red_color},
	{"icon": battery.LOW, "color": config["ui_color"]},
	{"icon": battery.HIGH, "color": config["ui_color"]},
	{"icon": battery.FULL, "color": green_color}
]

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
	
	widget_scroll_w = display_width // len(app_names)
	
	return app_names, app_paths, sd










#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Function Definitions: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def launch_app(app_path):
	#print(f'launching {app_path}')
	rtc = machine.RTC()
	rtc.memory(app_path)
	print(f"Launching '{app_path}...'")
	# reset clock speed to default. 
	machine.freq(160_000_000)
	time.sleep_ms(10)
	machine.reset()
	



def center_text_x(text, char_width = 16):
	"""
		Calculate the x coordinate to draw a text string, to make it horizontally centered. (plus the text width)
	"""
	str_width = len(text) * char_width
	# display is 240 px wide
	start_coord = display_width_half - (str_width // 2)
	
	return start_coord, str_width


def easeInCubic(x):
	return x * x * x

def easeOutCubic(x):
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


def read_battery_level(adc):
	"""
	read approx battery level on the adc and return as int range 0 (low) to 3 (high)
	"""
	raw_value = adc.read_uv() # vbat has a voltage divider of 1/2
	
	# more real-world data is needed to dial in battery level.
	# the original values were low, so they will be adjusted based on feedback.
	
	#originally 525000 (1.05v)
	if raw_value < 1575000: #3.15v
		return 0
	#originally 1050000 (2.1v)
	if raw_value < 1750000: #3.5v
		return 1
	#originally 1575000 (3.15v)
	if raw_value < 1925000: #3.85v
		return 2
	# 2100000 (4.2v)
	return 3 # 4.2v or higher


def erase_widgets(tft):
	tft.fill_rect(0, widget_scroll_y, display_width, widget_scroll_h, config["bg_color"]) # erase scrollbar
	tft.fill_rect(widget_clock_x, widget_clock_y, widget_clock_w, widget_clock_h, mid_color) # erase clock
	tft.fill_rect(widget_battery_x, widget_battery_y, widget_battery_w, widget_battery_h, mid_color) # erase battery

def draw_widgets(tft, app_selector_index, battlevel):
	#scroll bar
	tft.fill_rect((widget_scroll_w * app_selector_index), 133, widget_scroll_w, widget_scroll_h, mid_color)
	
	#clock
	_,_,_, hour_24, minute, _,_,_ = time.localtime()
	formatted_time, ampm = time_24_to_12(hour_24, minute)
	tft.text(fontsmall, formatted_time, widget_clock_x, widget_clock_y, config["ui_color"], mid_color)
	tft.text(fontsmall, ampm, widget_clock_x + 2 + (len(formatted_time) * 8), widget_clock_y, config["bg_color"], mid_color)
	
	#battery
	tft.bitmap_icons(battery, battery_widget[battlevel]["icon"], (mid_color,battery_widget[battlevel]["color"]), widget_battery_x, widget_battery_y)

def play_sound(beep, notes, time_ms):
	if config["ui_sound"]:
		beep.play(notes, time_ms, config["volume"])

#--------------------------------------------------------------------------------------------------
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main Loop: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#--------------------------------------------------------------------------------------------------




def main_loop():
	global config
	global mid_color, red_color, green_color
	global widget_scroll_w
	global battery_widget

	#bump up our clock speed so the UI feels smoother (240mhz is the max officially supported, but the default is 160mhz)
	machine.freq(240_000_000)
	
	
	# load our config asap to support other processes
	config_modified = False
	#load config
	try:
		with open("config.json", "r") as conf:
			config = json.loads(conf.read())
		mid_color = mh.mix_color565(config["bg_color"], config["ui_color"])
		red_color = mh.color565_shiftred(config["ui_color"])
		green_color = mh.color565_shiftgreen(config["ui_color"], 0.4)
	except:
		print("could not load settings from config.json. reloading default values.")
		config_modified = True
		with open("config.json", "w") as conf:
			conf.write(json.dumps(config))
		
	# sync our RTC on boot, if set in settings
	syncing_clock = config["sync_clock"]
	sync_ntp_attemps = 0
	connect_wifi_attemps = 0
	rtc = machine.RTC()
	
	#wifi loves to give unknown runtime errors, just try it twice:
	nic = None
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
	batt = ADC(10)
	batt.atten(ADC.ATTN_11DB)
	
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
		color_order=st7789.BGR)
	
	tft.vscrdef(40,display_width,40)
	tft.vscsad(target_vscsad)
	
	nonscroll_elements_displayed = False
	
	force_redraw_display = True
	
	#this is used as a flag to tell a future loop to redraw the frame mid-scroll animation
	delayed_redraw = False
	
	launching = False
	current_vscsad = 40
	
	scroll_direction = 0 #1 for right, -1 for left, 0 for center
	refresh_timer = 0
	
	#init the beeper!
	beep = beeper.Beeper()
	
	#starupp sound
	play_sound(beep, ('C3',
		('F3'),
		('A3'),
		('F3','A3','C3'),
		('F3','A3','C3')),130)
		
		
	#init diplsay
	tft.fill_rect(-40,0,280, display_height, config["bg_color"])
	tft.fill_rect(-40,0,280, 18, mid_color)
	
	
	while True:
		
		
		# ----------------------- check for key presses on the keyboard. Only if they weren't already pressed. --------------------------
		pressed_keys = kb.get_pressed_keys()
		if pressed_keys != prev_pressed_keys:
			
			# ~~~~~~ check if the arrow keys are newly pressed ~~~~~
			if "/" in pressed_keys and "/" not in prev_pressed_keys: # right arrow
				app_selector_index += 1
				
				#animation:

				scroll_direction = 1
				current_vscsad = target_vscsad
				play_sound(beep, (("C5","D4"),"A4"), 80)

				
			elif "," in pressed_keys and "," not in prev_pressed_keys: # left arrow
				app_selector_index -= 1
				
				#animation:
				
				scroll_direction = -1
				
				#this prevents multiple scrolls from messing up the animation
				current_vscsad = target_vscsad
				
				play_sound(beep, (("B3","C5"),"A4"), 80)
				
			
		
			# ~~~~~~~~~~ check if GO or ENTER are pressed ~~~~~~~~~~
			if "GO" in pressed_keys or "ENT" in pressed_keys:
				
				# special "settings" app options will have their own behaviour, otherwise launch the app
				if app_names[app_selector_index] == special_apps["ui_sound"]:
					
					if config["ui_sound"]: # currently unmuted, then mute
						config["ui_sound"] = False
						force_redraw_display = True
						config_modified = True
					else: # currently muted, then unmute
						config["ui_sound"] = True
						force_redraw_display = True
						play_sound(beep, ("C4","G4","G4"), 100)
						config_modified = True
				
				elif app_names[app_selector_index] == special_apps["reload_apps"]:
					app_names, app_paths, sd = scan_apps(sd)
					app_selector_index = 0
					current_vscsad = 42 # forces scroll animation triggers
					play_sound(beep, ('F3','A3','C3'),100)
						
				else: # ~~~~~~~~~~~~~~~~~~~ LAUNCH THE APP! ~~~~~~~~~~~~~~~~~~~~
					
					#save config if it has been changed:
					if config_modified:
						with open("config.json", "w") as conf:
							conf.write(json.dumps(config))
						
					# shut off the display
					tft.fill(black)
					tft.sleep_mode(True)
					Pin(38, Pin.OUT).value(0) #backlight off
					spi.deinit()
					
					if sd != None:
						try:
							sd.deinit()
						except:
							print("Tried to deinit SDCard, but failed.")
							
					play_sound(beep, ('C4','B4','C5','C5'),100)
						
					launch_app(app_paths[app_names[app_selector_index]])

			else: # keyboard shortcuts!
				for key in pressed_keys:
					# jump to letter:
					if key not in prev_pressed_keys and len(key) == 1: # filter special keys and repeated presses
						if key in 'abcdefghijklmnopqrstuvwxyz1234567890':
							#search for that letter in the app list
							for idx, name in enumerate(app_names):
								if name.lower().startswith(key):
									#animation:
									if app_selector_index > idx:
										scroll_direction = -1
									elif app_selector_index < idx:
										scroll_direction = 1
									current_vscsad = target_vscsad
									# go there!
									app_selector_index = idx
									play_sound(beep, ("G3"), 100)
									found_key = True
									break
				
			# once we parse the keypresses for this loop, we need to store them for next loop
			prev_pressed_keys = pressed_keys
		
		
		
		
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
		
		
		
		
		# if scrolling animation, move in the direction specified!
		if scroll_direction != 0:
			tft.vscsad(current_vscsad % display_width)
			if scroll_direction == 1:
				current_vscsad += math.floor(easeOutCubic((current_vscsad - 40) / display_width_half) * 10) + 5
				if current_vscsad >= 160:
					current_vscsad = -80
					scroll_direction = 0
			else:
				current_vscsad -= math.floor(easeOutCubic((current_vscsad - 40) / -display_width_half) * 10) + 5
				if current_vscsad <= -80:
					current_vscsad = 160
					scroll_direction = 0

				
		# if vscsad/scrolling is not centered, move it toward center!
		if scroll_direction == 0 and current_vscsad != target_vscsad:
			tft.vscsad(current_vscsad % display_width)
			if current_vscsad < target_vscsad:

				current_vscsad += (abs(current_vscsad - target_vscsad) // 8) + 1
			elif current_vscsad > target_vscsad:
				current_vscsad -= (abs(current_vscsad - target_vscsad) // 8) + 1

		
		
		# if we are scrolling, we should change some UI elements until we finish
		if nonscroll_elements_displayed and (current_vscsad != target_vscsad):
			erase_widgets(tft)
			nonscroll_elements_displayed = False
			
			
		elif nonscroll_elements_displayed == False and (current_vscsad == target_vscsad):
			battlevel = read_battery_level(batt)
			draw_widgets(tft, app_selector_index, battlevel)
			nonscroll_elements_displayed = True
			
		
		#refresh the text mid-scroll, or when forced
		if (delayed_redraw and scroll_direction == 0 ) or force_redraw_display:
			#delayed_redraw = False
			refresh_timer += 1
			
			if refresh_timer == 1 or force_redraw_display: # redraw text
				#crop text for display
				if len(prev_app_text) > 15:
					prev_app_text = prev_app_text[:12] + "..."
				if len(current_app_text) > 15:
					current_app_text = current_app_text[:12] + "..."
				
				#blackout the old text
				tft.fill_rect(-40, appname_y, 280, 32, config["bg_color"])
			
				#draw new text
				tft.text(font, current_app_text, center_text_x(current_app_text)[0], appname_y, config["ui_color"], config["bg_color"])
			
			if refresh_timer == 2 or force_redraw_display: # redraw icon
				refresh_timer = 0
				delayed_redraw = False
				
				#blackout old icon #TODO: delete this step when all text is replaced by icons
				tft.fill_rect(96, 30, 48, 36, config["bg_color"])
				
				#special menu options for settings
				if current_app_text == special_apps["ui_sound"]:
					label = toggle_labels[1 if config["ui_sound"] else 0]
					tft.text(font, label, center_text_x(label)[0], ui_icon_y, config["ui_color"], config["bg_color"])
						
				elif current_app_text == special_apps["reload_apps"]:
					tft.bitmap_icons(icons, icons.RELOAD, (config["bg_color"], config["ui_color"]), ui_icon_x, ui_icon_y)
					
				elif current_app_text == special_apps["settings"]:
					tft.bitmap_icons(icons, icons.GEAR, (config["bg_color"], config["ui_color"]), ui_icon_x, ui_icon_y)
					
				elif app_paths[app_names[app_selector_index]][:3] == "/sd":
					tft.bitmap_icons(icons, icons.SDCARD, (config["bg_color"], config["ui_color"]), ui_icon_x, ui_icon_y)
				else:
					tft.bitmap_icons(icons, icons.FLASH, (config["bg_color"], config["ui_color"]), ui_icon_x, ui_icon_y)
			

		
			
		
		#reset vars for next loop
		force_redraw_display = False
		
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
					
				elif sync_ntp_attemps >= max_ntp_attemps:
					nic.disconnect()
					nic.active(False) #shut off wifi
					syncing_clock = False
					print(f"Syncing RTC aborted after {sync_ntp_attemps} attemps")
				
			elif connect_wifi_attemps >= max_wifi_attemps:
				nic.disconnect()
				nic.active(False) #shut off wifi
				syncing_clock = False
				print(f"Connecting to wifi aborted after {connect_wifi_attemps} loops")
			else:
				connect_wifi_attemps += 1
		
# run the main loop!
main_loop()




