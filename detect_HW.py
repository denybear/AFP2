from screeninfo import get_monitors
from operator import attrgetter
import pygame
import pygame._sdl2.audio as sdl2_audio


#########################################################################
# This module is used to get information on the audio and video devices #
#########################################################################

colorNoError = [0, 128, 0]
colorError = [255, 0, 0]
colorWarning = [255, 165, 0]


# Manage audio HW: select the right audio device for outputing sound; for working on Raspberry, we use SDL2 instead of pyaudio (which works on windows)
def detectAudioHW (deviceName):
	# Inits
	isAudioHW = False
	audioColor = colorError
	primaryAudio = None
	
	pygame.init()
	devices = sdl2_audio.get_audio_device_names(False)
	print (devices)

	for dev in devices:
		# determine if we have the right device (USB sound card or I2S soundcard or embedded jack)
		for j in deviceName:				# deviceName list provided as an input can contain only subparts of actual device name
			if j in dev:					# we stop at first device found that is both in the list of HW device, and provided as parameter
				isAudioHW = True
				audioColor = colorNoError
				primaryAudio = dev
				break						# exit first loop
			else:
				continue
			break							# exit 2nd loop when 1st loop is finished

	# Leave
	pygame.quit()
	return isAudioHW, audioColor, primaryAudio
    

# Manage video HW: primary and secondary monitors
def detectVideoHW ():
	secondary_monitors = []
	primaryVideo = None
	secondaryVideo = None

	monitors = get_monitors ()
	for m in monitors:
		try:
			if m.is_primary:					# primary monitor will always get the control panel
				primaryVideo = m				# there should be only one primary monitor, no need for a list
				print (primaryVideo)
			else:
				secondary_monitors.append (m)
		except Exception as e:					# in case is_primary is not implemented (linux)
			if monitors.index (m) == 0:			# primary monitor is the first of the list, it will get the control panel
				primaryVideo = m				# there should be only one primary monitor, no need for a list
				print (primaryVideo)
			else:
				secondary_monitors.append (m)		

	# In case of 1 monitor only, we don't display the video
	if len (secondary_monitors) == 0:
		isVideoHW = False
		videoColor = colorError
		secondaryVideo = None

	else:
		# Go through the list of secondary monitors; we need 2 monitors only, one primary, one secondary.
		# In case of more than 2 secondary monitors, take only the one that has the biggest resolution (width, height), scrap the rest
		isVideoHW = True
		videoColor = colorNoError
		secondaryVideo = max(secondary_monitors, key = attrgetter('width', 'height'))
		print (secondaryVideo)

	return isVideoHW, videoColor, primaryVideo, secondaryVideo

