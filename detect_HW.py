from screeninfo import get_monitors
import pyaudio
from operator import attrgetter


#########################################################################
# This module is used to get information on the audio and video devices #
#########################################################################

colorNoError = [0, 128, 0]
colorError = [255, 0, 0]
colorWarning = [255, 165, 0]


# Manage audio HW: select the right audio device for outputing sound
def detectAudioHW (deviceName):
	# Initialize PyAudio
	p = pyaudio.PyAudio()
	isAudioHW = False
	audioColor = colorError
	primaryAudio = None
	# List all audio devices
	for i in range(p.get_device_count()):
		device_info = p.get_device_info_by_index(i)
		print(f"Device {i}: {device_info['name']}")

		# determine if we have the right device (USB sound card or I2S soundcard or embedded jack)
		for j in deviceName:				# deviceName list provided as an input can contain only subparts of actual device name
			if j in device_info ['name']:	# we stop at first device found that is both in the list of HW device, and provided as parameter
				isAudioHW = True
				audioColor = colorNoError
				primaryAudio = device_info
				break						# exit first loop
			else:
				continue
			break							# exit 2nd loop when 1st loop is finished

	# Terminate PyAudio
	p.terminate()
	return isAudioHW, audioColor, primaryAudio


# Manage video HW: primary and secondary monitors
def detectVideoHW ():
	secondary_monitors = []
	primaryVideo = None
	secondaryVideo = None

	for m in get_monitors():
		if m.is_primary:					# primary monitor will always get the control panel
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

