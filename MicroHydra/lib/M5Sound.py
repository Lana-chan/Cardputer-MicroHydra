"""
/*
 * ----------------------------------------------------------------------------
 * "THE BEER-WARE LICENSE" (Revision 42 modified):
 * <maple@maple.pet> wrote this file.  As long as you retain this notice and
 * my credit somewhere you can do whatever you want with this stuff.  If we
 * meet some day, and you think this stuff is worth it, you can buy me a beer
 * in return.
 * ----------------------------------------------------------------------------
 */
"""

from machine import Pin, I2S
import time

_PERIODS = [ # c0 thru a0 - how much to advance a sample pointer per frame for each note
	b'\x01\x00\x00\x00\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00',
	b'\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00',
	b'\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00'
]

_MIN_VOLUME = const(0)
_MAX_VOLUME = const(15)
@micropython.native
def _volume(volume):
	return _MAX_VOLUME - (_MIN_VOLUME if volume < _MIN_VOLUME else _MAX_VOLUME if volume > _MAX_VOLUME else volume)

@micropython.viper
def _vipmod(a:uint, b:uint) -> uint:
	while a >= b:
		a -= b
	return a

class Register:
	def __init__(self, buf_start=0, sample=None, sample_len=0, pointer=0, note=0, period=1, period_mult=4, loop=False, volume=0):
		self.buf_start = buf_start
		self.sample = sample
		self.pointer = pointer
		self.period = period
		self.note = note
		self.period_mult = period_mult
		self.sample_len = sample_len
		self.loop = loop
		self.volume = volume

	def copy(self):
		registers = Register()
		registers.buf_start = self.buf_start
		registers.sample = self.sample
		registers.pointer = self.pointer
		registers.period = self.period
		registers.note = self.note
		registers.period_mult = self.period_mult
		registers.sample_len = self.sample_len
		registers.loop = self.loop
		registers.volume = self.volume
		return registers
	
	def __str__(self):
		return f"{self.buf_start}: {self.sample} v:{self.volume} n:{self.note}"

class M5Sound:
	def __init__(self, buf_size=2048, rate=11025, channels=4, sck=41, ws=43, sd=42):
		self._output = I2S(
			1,
			sck=Pin(sck),
			ws=Pin(ws),
			sd=Pin(sd),
			mode=I2S.TX,
			bits=16,
			format=I2S.STEREO,
			rate=rate,
			ibuf=buf_size
		)
		
		self._rate = rate
		self._buf_size:int = buf_size
		self._buffer = bytearray(buf_size*2) # twice for stereo
		self.channels = channels
		self._registers = [Register() for _ in range(channels)]
		self._queues = [[] for _ in range(channels)]
		self._last_tick = 0
		self._output.irq(self._process_buffer)
		self._process_buffer(None)
		
	def __del__(self):
		self._output.deinit()

	@micropython.native
	def _gen_buf_start(self):
		return int((time.ticks_diff(time.ticks_us(), self._last_tick) // (1000000 / self._rate)) * 2) # stereo

	@micropython.native
	def play(self, sample, note=0, octave=4, volume=15, channel=0, loop=False):
		registers = Register(
			buf_start = self._gen_buf_start(),
			sample = sample,
			sample_len = len(sample) // 2,
			loop = loop,
			note = note % 12,
			period_mult = 2 ** (octave + (note // 12)),
			volume = volume
		)
		self._queues[channel].append(registers)

	@micropython.native
	def stop(self, channel=0):
		registers = Register() # default has empty sample
		registers.buf_start = self._gen_buf_start()
		self._queues[channel].append(registers)

	@micropython.native
	def setvolume(self, volume, channel=0):
		if len(self._queues[channel]) > 0:
			registers = self._queues[channel][-1].copy()
		else:
			registers = self._registers[channel].copy()
		registers.buf_start = self._gen_buf_start()
		registers.volume = volume
		self._queues[channel].append(registers)

	@micropython.viper
	def _clear_buffer(self):
		buf = ptr16(self._buffer)
		for i in range(0, int(self._buf_size)):
			buf[i] = 0

	@micropython.viper
	def _fill_buffer(self, registers, end:int) -> bool:
		buf = ptr16(self._buffer)
		start = 1 + int(registers.buf_start)
		smp = ptr16(registers.sample)
		slen = uint(registers.sample_len)
		ptr = uint(registers.pointer)
		per = ptr8(_PERIODS[registers.note])
		perlen = uint(len(_PERIODS[registers.note]))
		perptr = uint(registers.period)
		permult = int(registers.period_mult)
		vol = uint(_volume(registers.volume))
		loop = bool(registers.loop)
		for i in range(start, end, 2): # odd word: right channel only
			if ptr >= slen: # sample ended
				if not loop: # stop playing
					return False
				ptr = uint(_vipmod(ptr, slen)) # or loop
			bsmp = smp[ptr]
			# ladies and gentlemen, the two's complement
			bsmp = (bsmp & 0b1000000000000000) | ((bsmp & 0b0111111111111111) >> vol)
			if (bsmp & 0b1000000000000000) != 0:
				bsmp |= (0b111111111111111 << 15-vol)
			buf[i] += bsmp
			for _ in range(permult): # add together frame periods for different octaves
				ptr += per[perptr]
				perptr += uint(1)
				if perptr >= perlen:
					perptr = uint(0)
		registers.buf_start = 0
		registers.pointer = ptr
		registers.period = perptr
		return True

	@micropython.native
	def _process_buffer(self, arg):
		self._last_tick = time.ticks_us()
		self._output.write(self._buffer)
		self._clear_buffer()

		for ch in range(0, int(self.channels)):
			playing = True
			while playing:
				registers = self._registers[ch]

				end = self._buf_size
				if len(self._queues[ch]) > 0:
					if self._queues[ch][0].buf_start >= self._buf_size:
						self._queues[ch][0].buf_start -= self._buf_size
					else:
						end = self._queues[ch][0].buf_start
						self._registers[ch] = self._queues[ch].pop(0)
				else:
					playing = False

				if registers.sample:
					if not self._fill_buffer(registers, end):
						registers.sample = None