import sys
#sys.path.append('./')
import time
import lcd_interface

# Initialize the LCD display
lcd_interface.lcd_init()

# Print text on the first line
lcd_interface.lcd_string("Hello, World!", lcd_interface.LCD_LINE_1)

# Print text on the second line
lcd_interface.lcd_string("I2C LCD Display", lcd_interface.LCD_LINE_2)

# Wait for 2 seconds
time.sleep(2)

# Clear the display
lcd_interface.lcd_clear()
