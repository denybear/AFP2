# AFP2
Same as AFPlayer, but on a PI3 with 2-line LCD display

The project is at a stage where it works more or less (there may be a few remaining bugs), however there are many hurdles:
* Performances: Projet is very slow on a RPI3; it has never been tested on a RPI4 or 5.
* Rotary Encoder: currently, the rotary encoder reading is done in the main loop; as python is slow, we end up in missed readings, and a non-reactive UI. One way to work around this would be to manage rotary encoder through interrupts, however this has to be implemented.
* i2s audio support: Pygame only support SDL2, not ALSA. Even though an external board is supported by ALSA, and well managed by programs using ALSA (eg. VLC), this is not the case with pygame which only supports SDL2. SDL2 does not "recognize" the internal i2s audio board unless it is the default soundcard. One way to work around this is to remove the default internal cards (see below) so i2s card becomes default. Using an USB external soundcard is also a good alternative/complement.

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

   
also remove the default soundcards so i2s becomes default instead:
```
dtoverlay=vc4-fkms-v3d,audio=off
```
in newer systems, without the 'f', the syntax is different
```
dtoverlay=vc4-kms-v3d,noaudio
```
Save, then reboot. Because the default soundcards have been removed, i2s board is now the default soundcard and is recognized by SDL2/pygame.
I have also tried with a USB external soundcard, it works well as a secondary card, and is also recognized by SDL2/pygame.
