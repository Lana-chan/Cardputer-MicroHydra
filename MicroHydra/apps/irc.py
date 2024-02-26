import json, network, gc, time
import usocket as socket
from machine import Pin, SPI
from lib import st7789fbuf as st7789
from lib import keyboard
from font import vga1_8x16 as font

_BACKLOG_LEN = const(30)
_STATUS_NAME = const("Status")
_REFRESH_INPUT = 1
_REFRESH_FULL = 2

nic = None
config = {}
irc = None
spi = None
tft = None
kb = None
pressed_keys = []
prev_pressed_keys = []

def init_config():
	global config
	try:
		with open("config.json", "r") as conf:
			config_overlay = json.loads(conf.read())
			for key in config_overlay:
				config[key] = config_overlay[key]
		return True
	except:
		print("could not load settings from config.json")
	return False

def init_nic():
	global nic
	try:
		nic = network.WLAN(network.STA_IF)
	except RuntimeError as e:
		print(e)
		try:
			time.sleep(5)
			nic = network.WLAN(network.STA_IF)
		except RuntimeError as e:
			screen.tft.bitmap_text(TFT.font, "failed to setup WLAN!", 0, 0, st7789.RED)
			print("Wifi WLAN object couldnt be created. Gave this error:",e)
			import micropython
			print(micropython.mem_info(),micropython.qstr_info())
			return False

	if config["wifi_ssid"] == '':
		print("wifi information not found in config")
		return False

	if not nic.active(): # turn on wifi if it isn't already
		nic.active(True)
	if not nic.isconnected(): # try connecting
		try:
			nic.connect(config["wifi_ssid"], config["wifi_pass"])
			while not nic.isconnected():
				pass
		except OSError as e:
			print("wifi_sync_rtc had this error when connecting:",e)
			return False
	
	return True

def http_get(url):
    import socket
    _, _, host, path = url.split('/', 3)
    addr = socket.getaddrinfo(host, 80)[0][-1]
    s = socket.socket()
    s.connect(addr)
    s.send(bytes('GET /%s HTTP/1.0\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))
    while True:
        data = s.recv(100)
        if data:
            print(str(data, 'utf8'), end='')
        else:
            break
    s.close()

def parse_command(string):
	cmd, value = string[1:].split(' ', 1)
	cmd = cmd.upper()

	if cmd == "JOIN" or cmd == "PART":
		irc.send_cmd(cmd, value)

def handle_keyboard():
	global pressed_keys, prev_pressed_keys
	pressed_keys = kb.get_pressed_keys()
	channel = list(irc.channels)[irc.current_channel]
	for key in pressed_keys:
		if key not in prev_pressed_keys:
			if key == "LEFT": # left
				irc.current_channel -= 1
				irc.current_channel = irc.current_channel % len(irc.channels)
				screen.refresh_needed = _REFRESH_FULL
			elif key == "RIGHT": # right
				irc.current_channel += 1
				irc.current_channel = irc.current_channel % len(irc.channels)
				screen.refresh_needed = _REFRESH_FULL
			elif key == "ENT":
				input = irc.channels[channel].input_buffer.strip()
				if input.startswith('/'):
					parse_command(input)
				elif len(input) > 0:
					irc.send_msg()
					screen.refresh_needed = _REFRESH_FULL
			elif key == "BSPC":
				irc.channels[channel].input_buffer = irc.channels[channel].input_buffer[:-1]
				screen.refresh_needed = _REFRESH_INPUT
			elif key == "SPC":
				irc.channels[channel].input_buffer += ' '
				screen.refresh_needed = _REFRESH_INPUT
			elif key in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890.,<>?"\':;[{}]\\|-_=+!@#$%^&*()`~':
				irc.channels[channel].input_buffer += key
				screen.refresh_needed = _REFRESH_INPUT
			
	# once we parse the keypresses for this loop, we need to store them for next loop
	prev_pressed_keys = pressed_keys

class Channel:
	def __init__(self, name):
		self.name = name
		self.msg_buffer = []
		self.input_buffer = ""

	def append_line(self, text):
		split_lines = [text[i:i + screen.console_size[0]] for i in range(0, len(text), screen.console_size[0])]
		if len(split_lines) > 0:
			for line in split_lines:
				self.msg_buffer.append(line)
				if len(self.msg_buffer) > _BACKLOG_LEN:
					self.msg_buffer = self.msg_buffer[-_BACKLOG_LEN:]
					gc.collect()
			if list(irc.channels)[irc.current_channel] == self.name:
				screen.refresh_needed = _REFRESH_FULL

class IRC:
	def __init__(self, nickname, server, port, password=None):
		self.nickname = nickname
		self.server = server
		self.port = port
		self.password = password
		self.sock = None
		self.channels = {}
		self.buffer = ""
		self.current_channel = 0
		self.serveruser = None

	def send_cmd(self, cmd, message):
		command = f"{cmd} {message}\r\n".encode("utf-8")
		self.sock.send(command)

	def send_msg(self):
		channel = list(self.channels)[self.current_channel]
		self.send_cmd("PRIVMSG", f"{channel} :{self.channels[channel].input_buffer}")
		self.channels[channel].append_line(f"<{self.nickname}> {self.channels[channel].input_buffer}")
		self.channels[channel].input_buffer = ""

	def connect(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.connect((self.server, self.port))
		self.sock.setblocking(False)
		if self.password:
			self.send_cmd("PASS", self.password)
		self.send_cmd("NICK", self.nickname)
		self.send_cmd("USER", f"{self.nickname} * * :{self.nickname}")
		self.channels[_STATUS_NAME] = Channel(_STATUS_NAME)

	def receive(self):
		try:
			self.buffer += self.sock.recv(512).decode("utf-8")
		except OSError as e:
			return
		lines = self.buffer.split('\r\n')
		self.buffer = lines[-1]

		for resp in lines[:-1]:
			if resp.strip() == "":
				continue
			print(resp)
			user = None
			if resp.startswith(':'):
				user, cmd, value = resp.split(' ', 2)
			else:
				cmd, value = resp.split(' ', 1)
			self.parse(user, cmd, value)

	def parse(self, user, cmd, value):
		cmd = cmd.upper()
		nick = self.parse_nick(user)
		
		if cmd == "NOTICE" or cmd == "001":
			if not self.serveruser:
				self.serveruser = user
		
		if user == self.serveruser:
			self.channels[_STATUS_NAME].append_line(value.split(' ', 1)[1])
		
		if cmd == "PING":
			self.send_cmd("PONG", value)
		elif cmd == "PRIVMSG":
			channel, msg = value.split(' ', 1)
			if self.channels[channel]:
				msg = msg[1:]
				self.channels[channel].append_line(f"<{nick}> {msg}")
		elif cmd == "JOIN":
			if value.startswith(':') or value.startswith('#'):
				channel = value[1:] if value.startswith(':') else value
				if nick == self.nickname:
					self.channels[channel] = Channel(channel)
					self.channels[channel].append_line(f"* Joined {channel}")
				else:
					self.channels[channel].append_line(f"* {nick} joined {channel}")
		elif cmd == "PART":
			if value.startswith(':') or value.startswith('#'):
				channel = value[1:] if value.startswith(':') else value
				if nick == self.nickname:
					self.channels[channel].append_line(f"* Left {channel}")
					self.channels.pop(channel)
				else:
					self.channels[channel].append_line(f"* {nick} left {channel}")
		elif cmd == "376" or cmd == "422": # End of MOTD or No MOTD, we're done connecting
			# start up cmds here
			pass

	def parse_nick(self, user):
		if not user: return None
		return user.split('!')[0].strip(':')

class TFT():
	display_width = const(240)
	display_height = const(135)
	font = font

	def __init__(self):
		self.cursor = [0, 0]
		self.refresh_needed = 0
		global spi
		spi = SPI(1, baudrate=40000000, sck=Pin(36), mosi=Pin(35), miso=None)
		self.tft = st7789.ST7789(
			spi,
			TFT.display_height,
			TFT.display_width,
			reset=Pin(33, Pin.OUT),
			cs=Pin(37, Pin.OUT),
			dc=Pin(34, Pin.OUT),
			backlight=Pin(38, Pin.OUT),
			rotation=1,
			color_order=st7789.BGR
		)
		#self.tft.offset(40, 53)
		#self.tft.init()
		self.console_size = (TFT.display_width // TFT.font.WIDTH, TFT.display_height // TFT.font.HEIGHT)
		self.tft.fill_rect(0, 0, TFT.display_width, TFT.display_height, 0)

	def refresh(self):
		if self.refresh_needed != 0 and len(irc.channels) > 0:
			channel = irc.channels[list(irc.channels)[irc.current_channel]]

			if self.refresh_needed == _REFRESH_FULL:
				self.tft.fill_rect(0, 0, TFT.display_width, TFT.display_height, 0)
				line_index = len(channel.msg_buffer)-1
				self.cursor[1] = self.console_size[1]-2
				while self.cursor[1] >= 0 and line_index >= 0:
					self.tft.bitmap_text(TFT.font, channel.msg_buffer[line_index], 0, self.cursor[1] * TFT.font.HEIGHT, st7789.WHITE)
					self.cursor[1] -= 1
					line_index -= 1
			
			self.cursor[1] = self.console_size[1]-1
			if self.refresh_needed == _REFRESH_INPUT:
				self.tft.fill_rect(0, self.cursor[1] * TFT.font.HEIGHT, TFT.display_width, TFT.font.HEIGHT, 0)

			input_line = f"{channel.name}> {channel.input_buffer}"
			if len(input_line) > self.console_size[0]:
				input_line = input_line[-self.console_size[0]:]
			self.tft.bitmap_text(TFT.font, input_line, 0, self.cursor[1] * TFT.font.HEIGHT, st7789.YELLOW)

			self.refresh_needed = 0
			self.tft.show()

def init():
	global irc, screen, kb
	screen = TFT()

	if not init_config():
		screen.tft.bitmap_text(TFT.font, "failed to open config!", 0, 0, st7789.RED)
		return False
	if not init_nic():
		screen.tft.bitmap_text(TFT.font, "no wifi config found!", 0, 0, st7789.RED)
		return False
	
	kb = keyboard.KeyBoard()
	
	try:
		if config["irc_password"] and config["irc_pass"] != "":
			irc = IRC(config["irc_nick"], config["irc_server"], config["irc_port"], config["irc_pass"])
		else:
			irc = IRC(config["irc_nick"], config["irc_server"], config["irc_port"])
	except:
		screen.tft.bitmap_text(TFT.font, "no irc config found!", 0, 0, st7789.RED)
		return False
	
	irc.connect()
	screen.refresh_needed = _REFRESH_FULL
	loop()

def loop():
	while True:
		irc.receive()

		handle_keyboard()

		screen.refresh()

		time.sleep_ms(5)

init()