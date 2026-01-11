import smbus
import time

I2C_ADDR = 0x27
LCD_WIDTH = 16

LCD_CHR = 1
LCD_CMD = 0

LCD_LINE_1 = 0x80
LCD_LINE_2 = 0xC0

LCD_BACKLIGHT = 0x08

ENABLE = 0b00000100

E_PULSE = 0.0005
E_DELAY = 0.0005

bus = smbus.SMBus(1)

def lcd_init():
	lcd_byte(0x33, LCD_CMD)		# 4-bit init sequence (per HD44780)
	lcd_byte(0x32, LCD_CMD)		# 4-bit init sequence (per HD44780)
	lcd_byte(0x06, LCD_CMD)		# entry mode: increment, no shift
	lcd_byte(0x0C, LCD_CMD)		# display ON, cursor OFF, blink OFF
	lcd_byte(0x28, LCD_CMD)		# 4 bit, 2 lines, 5x8 chars
	lcd_byte(0x01, LCD_CMD)		# clear display
	time.sleep(E_DELAY)

def lcd_byte(bits, mode):
	bits_high = mode | (bits & 0xF0) | LCD_BACKLIGHT
	bits_low = mode | ((bits << 4) & 0xF0) | LCD_BACKLIGHT

	bus.write_byte(I2C_ADDR, bits_high)
	lcd_toggle_enable(bits_high)

	bus.write_byte(I2C_ADDR, bits_low)
	lcd_toggle_enable(bits_low)

def lcd_toggle_enable(bits):
	time.sleep(E_DELAY)
	bus.write_byte(I2C_ADDR, (bits | ENABLE))
	time.sleep(E_PULSE)
	bus.write_byte(I2C_ADDR, (bits & ~ENABLE))
	time.sleep(E_DELAY)

def lcd_string(message, line):
	message = message.ljust(LCD_WIDTH, " ")

	lcd_byte(line, LCD_CMD)

	for i in range(LCD_WIDTH):
		lcd_byte(ord(message[i]), LCD_CHR)

def lcd_clear():
	lcd_byte(0x01, LCD_CMD)

def lcd_load_char(location, char):
	
	location = (location & 0x07) << 3
	lcd_byte(0x40 | location, LCD_CMD)
	for item in char:
		lcd_byte(item & 0x1F, LCD_CHR)
	time.sleep(E_DELAY)
