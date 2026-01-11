# left do do: sample keys, sample play

# Config 2: raspi with 2*16 char display as control screen, rotary encoder for track/sample selection, i2s board for sound, optional HDMI display for video
import sys
import time
sys.path.append('./')
import pygame
import cv2
import os
import json
import random
import threading
from collections import deque
import RPi.GPIO as GPIO
from detect_HW import detectAudioHW
from detect_HW import detectVideoHW
from playlist_update import sync_remote_file
import lcd_interface

# Global variables
audio_thread = None
cap = None
videoPath = "./video/"
audioPath = "./audio/"
running = True
playing = False
counter = 0
audioVolume = 0.5
videoRate = 0.5
playListIndex = 0
keyGPIO = []
keyGPIOName = []
rotaryGPIO = [17, 18, 27]
rotaryGPIOName = ["CLK", "DT", "SW"]
playChar = [
	0b00000,
	0b01000,
	0b01100,
	0b01110,
	0b01111,
	0b01110,
	0b01100,
	0b01000,
]
stopChar = [
	0b00000,
	0b00000,
	0b00000,
	0b01111,
	0b01111,
	0b01111,
	0b01111,
	0b00000,
]



# functions for raspi key capture and rotary capture
def init_gpio():

	# Set GPIO mode (BCM or BOARD)
	GPIO.setmode(GPIO.BCM)  # Use GPIO numbering (BCM)
	# GPIO.setmode(GPIO.BOARD)  # Use physical pin numbering
	#GPIO.setup(23, GPIO.OUT)  # Pin 23 as output

	# Set up keys GPIOs
	# Pull-up mode : when idle, GPIO is considered at +3V. Switch can be connected to GND, and when closed, GPIO will fall down to GND
	for pin in keyGPIO:
		GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)		# Pin as input with pull-up resistor

	# Set up rotary GPIOs
	for pin in rotaryGPIO:
		GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)		# Pin as input with pull-up resistor
		"""
		# if the above does not work, use the below
		pinName = rotaryGPIOName [rotaryGPIO.index (pin)]
		if pinName == "SW":
			GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)		# Pin as input with pull-up resistor
		else:
			GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)	# Pin as input with pull-down resistor
		"""

def rotary_gpio(name):
	for pin in rotaryGPIOName:
		if pin == name:
			return rotaryGPIO [rotaryGPIOName.index (pin)]




# class for handling events in the main loop
class Event:
	def __init__(self, label, values):
		if not isinstance(values, (list, dict)):
			raise ValueError("Values must be a list or dictionary.")
		self.label = label
		self.values = values

class EventQueue:
	def __init__(self):
		self.queue = deque()

	def record_event(self, label, values):
		"""Create an Event and add it to the queue."""
		event = Event(label, values)
		self.queue.append(event)

	def get_next_event(self):
		"""Retrieve and remove the next Event from the queue."""
		if self.queue:
			return self.queue.popleft()
		return None

	def peek_next_event(self):
		"""Retrieve the next Event without removing it."""
		if self.queue:
			return self.queue[0]
		return None

	def is_empty(self):
		"""Check if the queue is empty."""
		return len(self.queue) == 0

	def size(self):
		"""Return the number of events in the queue."""
		return len(self.queue)


# object representing a tuple: name of the song, name of the video/picture, name of samples 
class Song:
	def __init__(self, song="", video="", sample=["","","","","","","","",""], startPosition="beginning"):
		self.song = song
		self.video = video
		self.sample = sample
		self.startPosition = startPosition

	def __repr__(self):
		return f"Song(song={self.song}, video={self.video}, sample={self.sample}, startPosition={self.startPosition})"


# function for the audio thread
def play_audio(audio_file):
	try:
		pygame.mixer.music.load(audio_file)
	except pygame.error:
		# file does not exist
		return False
	pygame.mixer.music.set_endevent(pygame.USEREVENT)	# pygame event is triggered after playing is complete
	pygame.mixer.music.play()
	return True

def stop_audio():
	pygame.mixer.music.stop()

def start_audio_thread(audio_file):
	global audio_thread
	stop_audio()

	if not os.path.isfile(audio_file):
		# file does not exist
		return False

	audio_thread = threading.Thread(target=play_audio, args=(audio_file,))
	audio_thread.start()
	return True


# functions for managing the playlisyt
# returns length of the playlist
def playlist_length (playList)
	count = 0
	for item in playList:
		# increase count for every sample found
		if len (item.sample) == 0:
			count += 1
		else:
			count += len (item.sample)
	return count

# returns, from counter value, the index in playlist, current song and current sample in the playlist
def playlist_from_counter (playList, counter)
	count = 0
	for item in playList:
		if len (item.sample) == 0:
			count += 1
			if count == counter:
				return playList.index(item), item.song, ""
		else:
			for sample in item.sample:
				count+=1
				if count == counter:
					return playList.index(item), item.song, sample
	return 0

	
########
# MAIN #
########

# check online & update playlist if required
updated, msg = sync_remote_file(
	"https://github.com/denybear/AFPlayer/blob/main/playlist.json",
	local_filename="playlist.json",  # will save into the current directory
	timeout=3.0
)
print(updated, msg)

# init raspi hardware
init_gpio ()
rotaryCurrentState = (GPIO.input(rotary_gpio("CLK")) << 1) | GPIO.input(rotary_gpio("DT"))

# Initialize the LCD display, load custom chars
lcd_interface.lcd_init()
lcd_interface.lcd_load_char(0, stopChar)
lcd_interface.lcd_load_char(1, playChar)

# Load the JSON data from the file
with open('./playlist.json', 'r', encoding='utf-8') as file:
	data = json.load(file)

# Create a list of Song objects
playList = [Song(item['song'], item['video'], item['sample'], item['startPosition']) for item in data]

# Manage audio HW: select the right audio device for outputing sound; we can enter several devices (or device sub-names), the first one found will be used
# HERE: we should use i2s audio driver
isAudioHW, audioColor, primaryAudio = detectAudioHW (["Haut-parleur/Ecouteurs (Realtek High Definition Audio)", "Headphones 1 (Realtek HD Audio 2nd output with SST)"])

# Manage video HW: primary and secondary monitors
isVideoHW, videoColor, primaryVideo, secondaryVideo = detectVideoHW ()
# adapt HW detection to config 2; in case a primary screen is found, it will be used as a secondary monitor to display video
if primaryVideo is not None:
	secondaryVideo = primaryVideo
	isVideoHW = True


# Initialize Pygame
pygame.init()
pygame.mixer.init(devicename=primaryAudio['name'])
pygame.mixer.music.set_volume (audioVolume)

# Create windows

# we start with secondary monitor as we want the primary monitor (pygame control panel) to get the full control over UI
# secondary monitor will get the video
# Create a named window; the flags control window behavior
# In this case, we don't want any title bar or border
if isVideoHW:
	cv2.namedWindow('Video', cv2.WND_PROP_FULLSCREEN)
	cv2.setWindowProperty('Video', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
	# Resize the window to a specific size (width, height) : this is useless as we have WINDOW_FULLSCREEN as a window property
	#cv2.resizeWindow('Video', secondaryVideo.width, secondaryVideo.height)
	# Move the window to the secondary monitor (secondaryVideo.x, secondaryVideo.y)
	cv2.moveWindow('Video', secondaryVideo.x, secondaryVideo.y)

# force all inputs to be in the pygame window, and hide mouse
#pygame.mouse.set_visible (False)
#pygame.event.set_grab (True)
#pygame.display.set_caption("Song Info Display")


# Main loop
eq = EventQueue()		# event queue to manage the events happening in the main loop
# force display of 1st song in playlist and video
eq.record_event("key", ["first song"])

while running:

	# Handle Pygame events
	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			running = False

		elif event.type == pygame.USEREVENT:
			# audio playing is complete, let's record an event to stop playing and update the display
			eq.record_event("audio", ["stop"])		
			
		elif event.type == pygame.KEYDOWN:
			# key press pygame event
			# numpad keys are (top left to bottom right): numlock, [/], [*], [-], [7], [8], [9], [+], [4], [5], [6], backspace, [1], [2], [3], ,[0], 0 pressed 3 times (for 000 key), [.], enter
			keyMapping = {"q":["quit"], "p":["previous"], "backspace":["previous"], "n":["next"], "enter":["next"], "[-]":["vol-"], "[+]":["vol+"], "a":["vol-"], "z":["vol+"], "e":["vid-"], "r":["vid+"], "1":["sample","1"], "numlock":["sample","1"], "2":["sample","2"], "[/]":["sample","2"], "3":["sample","3"], "[*]":["sample","3"], "4":["sample","4"], "[7]":["sample","4"], "5":["sample","5"], "[8]":["sample","5"], "6":["sample","6"], "[9]":["sample","6"]}

			keyPressed = pygame.key.name(event.key)
			try:
				eq.record_event("key", keyMapping [keyPressed])
			except KeyError:
				pass


	# Handle main loop events
	next_event = eq.get_next_event()
	if next_event:		# make sure there is an event to process

		# display events
		if next_event.label == "display":
			# Display on 2*16 display
			# HERE: we could display the sample name in reverse video in case it is playing???
			# top left : playList [playListPrevious].song
			# top right : playList [playListNext].song
			# bottom left : playList [playListIndex].song
			# bottom right: playList [playListIndex].sample

			# Clear the display (no use as we write 2 complete lines of text)
			#lcd_interface.lcd_clear()

			# Print text on the first line	
			# Take first 7 characters of str1 and pad with spaces if needed
			part1 = playList [playListPrevious].song[:7].ljust(7)
			# Take first 8 characters of str2 and pad with spaces if needed
			part2 = playList [playListNext].song[:7].ljust(7)
			lcd_interface.lcd_string(part1 + '  ' + part2, lcd_interface.LCD_LINE_1)

			# Print text on the second line
			# Trim the string to a maximum of 16 characters
			idx, sg, sp = playlist_from_counter (playList, counter)
			part1 = sg[:7].ljust(7)
			part2 = sp.ljust(7)
			#trimmed = sg[:16]
			# Centre the string and pad with spaces to make it exactly 16 characters
			#return trimmed.center(16)
			if playing:				# custom char play or stop
				playIcon = chr(1)
			else:
				playIcon = chr(0)			
			lcd_interface.lcd_string(part1 + ' ' + playIcon + part2, lcd_interface.LCD_LINE_2)


		# key events
		if next_event.label == "key":

			# quit
			if next_event.values [0] == "quit":
				running = False
				break

			# previous
			if next_event.values [0] == "previous" or next_event.values [0] == "first song":
				# get video file name that is currently playing
				try:
					previousVideoFileName = videoPath + playList [playListIndex].video
				except (ValueError, IndexError):
					previousVideoFileName = ""
				# in case of 1st song, force display of video by specifying no previous video
				if next_event.values [0] == "first song":
					previousVideoFileName = ""
				# previous in playlist
				counter = max (counter - 1, 0)
				playListIndex, sg, sp = playlist_from_counter (playList, counter)
				playListPrevious = max(playListIndex - 1, 0)
				playListNext = min(playListIndex + 1, len(playList) - 1)
				# record new event to update the display
				eq.record_event("display", [])
				
				# record event to play video
				try:
					videoFileName = videoPath + playList [playListIndex].video
				except (ValueError, IndexError):
					videoFileName = ""
				try:
					startPos = playList [playListIndex].startPosition
				except (ValueError, IndexError):
					startPos = "beginning"
				eq.record_event("video", ["play", videoFileName, previousVideoFileName, startPos])

			# next
			if next_event.values [0] == "next":
				# get video file name that is currently playing
				try:
					previousVideoFileName = videoPath + playList [playListIndex].video
				except (ValueError, IndexError):
					previousVideoFileName = ""
				# next in playlist
				counter = min (counter + 1, playlist_length (playList))
				playListIndex, sg, sp = playlist_from_counter (playList, counter)
				playListPrevious = max(playListIndex - 1, 0)
				playListNext = min(playListIndex + 1, len(playList) - 1)
				# record new event to update the display
				eq.record_event("display", [])
				# record event to play video
				try:
					videoFileName = videoPath + playList [playListIndex].video
				except (ValueError, IndexError):
					videoFileName = ""
				try:
					startPos = playList [playListIndex].startPosition
				except (ValueError, IndexError):
					startPos = "beginning"
				eq.record_event("video", ["play", videoFileName, previousVideoFileName, startPos])

			# sample keys
			if next_event.values [0] == "sample":
				# proceed only if sample 1 is keyed, not the others
				if next_event.values [1] == "1":
					# get actual sample filename from playlist; check whether empty
					idx, sg, sp = playlist_from_counter (playList, counter)
					if sp != "":
						sampleFileName = audioPath + sp
					else:
						sampleFileName = ""

					# check if playing or not; if playing, we should stop the audio first (update of the display will be done in stop event processing)
					if playing:
						eq.record_event("audio", ["stop"])
					# if not playing, then we should initiate playing
					else:
						sampleString = "sample" + next_event.values [1]
						eq.record_event("audio", ["play", sampleString, sampleFileName])

			# audio volume -, audio volume +, video rate -, video rate +
			if next_event.values [0] in ("vol-","vol+","vid-","vid+"):
			
				if next_event.values [0] == "vol-":
					audioVolume = max (0, audioVolume - 0.02)
					if isAudioHW:
						pygame.mixer.music.set_volume (audioVolume)

				# audio volume +
				if next_event.values [0] == "vol+":
					audioVolume = min (audioVolume + 0.02, 1.0)
					if isAudioHW:
						pygame.mixer.music.set_volume (audioVolume)

				# video rate -
				if next_event.values [0] == "vid-":
					videoRate = max (0.1, videoRate - 0.02) 	# lowest video rate would be 10%, ie. 50ms wait per frame 

				# video rate +
				if next_event.values [0] == "vid+":
					videoRate = min (videoRate + 0.02, 1.0)	 # highest video rate would be 100%, ie. 5ms wait per frame


		# audio events
		if next_event.label == "audio":

			# stop
			if next_event.values [0] == "stop":
				if isAudioHW: stop_audio()
				playing = False
				# record new event to update the display
				eq.record_event("display", [])

			# play
			if next_event.values [0] == "play":
				# attempt to open audio file and play it
				sampleString = next_event.values [1]
				sampleFileName = next_event.values [2]
				playing = start_audio_thread (sampleFileName) if isAudioHW else False
				eq.record_event("display", [])


		# video events
		if next_event.label == "video":

			# play
			if next_event.values [0] == "play":
				videoFileName = next_event.values [1]
				previousVideoFileName = next_event.values [2]
				# make sure video HW is on
				if isVideoHW:
					# if video is same as previous, then don't restart video... we just carry on showing
					if videoFileName != previousVideoFileName:
						cap = cv2.VideoCapture(videoFileName)						# cap.isOpened() returns False if file does not exist
						# in case file does not exists, cap.isOpened () will return False
						if not cap.isOpened():
							# file does not exist, update display
							pass
						else:
							# file exists, update display
							# determine startPos, and set it to video
							if next_event.values [3] == "beginning":
								startPos = 0
							else:
								startPos = random.randint (0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
							# set start position
							cap.set(cv2.CAP_PROP_POS_FRAMES, startPos)				

						eq.record_event("display", [])



	# Perform non-event based functions, ie. video display and key capture

	# display video (if exists)
	if isVideoHW and (cap is not None and cap.isOpened()):
		ret, frame = cap.read()

		# If the video ends, restart it
		if not ret:
			cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
			continue
		# display video frame
		cv2.imshow("Video", frame)
		# Wait for a key press for 1 millisecond; but don't capture it. waitKey() is mandatory so the image is displayed in opencv2
		cv2.waitKey(1)
		# Wait for some milliseconds, based on video rate : 5ms at full rate (1.0), 10ms at 50%, 20ms at 25%, 25ms at 20%
		time.sleep (0.005 / videoRate)


	#####################################################
	# THIS PART DEALS WITH RASPI KEY AND ROTARY SUPPORT #
	#####################################################

	# check if raspi keypress or rotary

	# RASPI KEYS
	# Read the state of each GPIO to determine which are on and off, ie. which key is pressed or not
	# Given for Config 2, there are not keys, this part is never executed
	for pin in keyGPIO:
		# LOW means key is pressed, HIGH means key is not pressed; we change this so True=pressed, False=not pressed
		if not GPIO.input(pin):
			# key is pressed, add key event
			eq.record_event("key", keyGPIOName [keyGPIO.index (pin)])

	# RASPI ROTARY
	# check if we should progress in playlist / samples
	# button would play / stop sample
	rotaryCurrentState = (GPIO.input(rotary_gpio("CLK")) << 1) | GPIO.input(rotary_gpio("DT"))

	key = (rotaryLastState << 2) | rotaryCurrentState
	if key == 0b1110:
		counter -= 1
	elif key in (0b0001, 0b0111, 0b1000):
		pass
	elif key == 0b1101:
		counter += 1
	elif key in (0b0100, 0b1011, 0b0010):
		pass
	rotaryLastState = rotaryCurrentState

	# cap counter value
	counter = max (0, counter)
	counter = min (counter, playlist_length (playList))

	# Detect button press
	#if GPIO.input(SW) == GPIO.LOW:
	if not GPIO.input(rotary_gpio("SW")):
		eq.record_event("key", ["sample", "1"])		# simulate pressing on sample "1" key
		# no need for display event, as key contain its own display events
		#sleep(0.3)  # Debounce delay


# Cleanup
GPIO.cleanup()		# Clean up GPIO on exit

if isAudioHW: stop_audio()
if isVideoHW and cap is not None:
	cap.release()
cv2.destroyAllWindows()
pygame.mixer.music.stop()
# Disable input grabbing before exiting
pygame.event.set_grab(False)
pygame.mouse.set_visible (True)
pygame.quit()
