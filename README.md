# AFP2
Same as AFPlayer, but on a PI3 with 2-line LCD display

The project is at a stage where it works more or less (there may be a few remaining bugs), however there are many hurdles:
* Performances: Projet is very slow on a RPI3; it has never been tested on a RPI4 or 5.
* Rotary Encoder: currently, the rotary encoder reading is done in the main loop; as python is slow, we end up in missed readings, and a non-reactive UI. One way to work around this would be to manage rotary encoder through interrupts, however this has to be implemented.
* i2s audio support: Pygame only support SDL2, not ALSA. Even though an external board is supported by ALSA, and well managed by programs using ALSA (eg. VLC), this is not the case with pygame which only supports SDL2. SDL2 does not "recognize" the internal i2s audio board. One way to work around this could be to use an USB external soundcard (yet to be tested). Another way is to modify a bunch of PI OS files, but this is not working well based on my preliminary tests.

## Getting internal i2s board recognized by PI OS
```
sudo nano /boot/firmware/config.txt
```
At the top of the file, uncomment these lines to enable I2C and I2S:
```
dtparam=i2s=on
```
Then, at the bottom of the file, add this line:
```
#dtparam=audio=on
dtoverlay=hifiberry-dac
```
(you can also try with dtoverlay=pcm5102a)

   
also remove the HDMI sound:
```
dtoverlay=vc4-fkms-v3d,audio=off
```
in newer systems, without the 'f', the syntax is different
```
dtoverlay=vc4-kms-v3d,noaudio
```
Save, then reboot.

## Getting SDL2 recognizing ALSA devices
Create a /etc/asound.conf file (global settings ) or ~/.asoundrc file (local settings) with the following:
```
# ---- Virtual device for SDL ----
pcm.sdl_device {
    type plug
    slave {
        pcm "hw:1,0"     # <-- replace with your target ALSA device
        rate 48000
        channels 2
    }
}

# Optional: override default device SDL opens
pcm.!default {
    type asym
    playback.pcm "sdl_device"
    capture.pcm  "hw:1,0"
}
```
then in shell, type the following:
```
export SDL_AUDIODRIVER=alsa
export SDL_AUDIO_ALSA_DEFAULT_DEVICE="hw:1,0"
```

