import wave
import numpy
import os
import re
import threading
import pyaudio
import rtmidi_python as rtmidi
import samplerbox_audio

import smbus
import LCD1602 as LCD
import time

from gpiozero import Button
from signal import pause

MAX_POLYPHONY = 80
SAMPLES_DIR = '/home/pi/Samples'

class PlayingSound:
    def __init__(self, sound, note, velocity):
        self.sound = sound
        self.pos = 0
        self.fadeoutpos = 0
        self.isfadeout = False
        self.note = note
        self.velocity = velocity

    def fadeout(self, i):
        self.isfadeout = True

    def stop(self):
        try:
            playingsounds.remove(self)
        except:
            pass

class Sound:
    def __init__(self, filename, midinote):
        wf = wave.open(filename, 'rb')
        self.fname = filename
        self.midinote = midinote
        self.nframes = wf.getnframes()

        self.data = self.frames2array(wf.readframes(wf.getnframes()),
                                      wf.getsampwidth(),
                                      wf.getnchannels())
        wf.close()

    def play(self, note, velocity):
        snd = PlayingSound(self, note, velocity)
        print snd
        playingsounds.append(snd)
        return snd

    def frames2array(self, data, sampwidth, numchan):
        if sampwidth == 2:
            npdata = numpy.fromstring(data, dtype = numpy.int16)
        else:
            print 'sampwidth error'

        if numchan == 1:
            npdata = numpy.repeat(npdata, 2)
            
        return npdata

FADEOUTLENGTH = 30000
FADEOUT = numpy.linspace(1., 0., FADEOUTLENGTH)
FADEOUT = numpy.power(FADEOUT, 6)
FADEOUT = numpy.append(FADEOUT, numpy.zeros(FADEOUTLENGTH, numpy.float32)).astype(numpy.float32)
SPEED = numpy.power(2, numpy.arange(0.0, 84.0)/12).astype(numpy.float32)

playingsounds = []
samples = {}
playingnotes= {}
sustainplayingnotes = []
sustain = False
globalvolume = 10 ** (-12.0/20)
globaltranspose = 0



##AUDIO AND MIDI CALLBACKS

def AudioCallback(in_data, frame_count, time_info, status):
    global playingsounds
    rmlist = []
    playingsounds = playingsounds[-MAX_POLYPHONY:]
    b = samplerbox_audio.mixaudiobuffers(playingsounds, rmlist, frame_count, FADEOUT, FADEOUTLENGTH, SPEED)
    for e in rmlist:
        try:
            playingsounds.remove(e)
        except:
            pass
    b *= globalvolume
    odata = (b.astype(numpy.int16)).tostring()
    return (odata, pyaudio.paContinue)

def MidiCallback(message, time_stamp):
    global playingnotes, sustain, sustainplayingnotes
    global preset
    
    print message
    messagetype = message[0] >> 4
    messagechannel = (message[0] & 15) + 1
    print hex(messagetype)
    note = message[1] if len(message) > 1 else None
    midinote = note
    print note
    velocity = message[2] if len(message) > 2 else None
    print velocity

    if messagetype == 9 and velocity == 0:
        messagetype = 8

    if messagetype == 9: #note on
        midinote += globaltranspose
        try:
            playingnotes.setdefault(midinote, []).append(samples[midinote].play(midinote, velocity))
        except:
            pass

    elif messagetype == 8: #note off
        midinote += globaltranspose
        if midinote in playingnotes:
            for n in playingnotes[midinote]:
                if sustain:
                    sustainplayingnotes.append(n)
                    pass
                else:
                    n.fadeout(50)
            playingnotes[midinote] = []
    
    elif messagetype == 11:
        if message[1] == 1:
            modulation = message[2]
            print 'Modulation ' + str(modulation)
        elif message[1] == 64:
            print 'Sustain Pedal'
            if message[2] == 127:
                print 'Sustain on'
                sustain = True
            else:
                print 'Suatain off'
                for n in sustainplayingnotes:
                    n.fadeout(50)
                sustainplayingnotes = []
                sustain = False
        else:
            print 'None'

    elif messagetype == 14:
##        print hex(message[1]) + ' ' + hex(message[2])
        pitchbend = message[1]+(message[2]<<7)
        print 'pitchbend ' + str(pitchbend)


##Loading

LoadingThread = None
LoadingInterrupt = False

def LoadSamples():
    global LoadingThread
    global LoadingInterrupt

    if LoadingThread:
        LoadingInterrupt = True
        LoadingThread.join()
        LoadingThread = None

    LoadingThread = threading.Thread(target = ActuallyLoad)
    LoadingThread.daemon = True
    LoadingThread.start()

def ActuallyLoad():
    global preset
    global samples
    samples = {}

    basename = next((f for f in os.listdir(SAMPLES_DIR) if f.startswith("%s" %preset)), None)
    if basename:
        dirname = os.path.join(SAMPLES_DIR, basename)
    if not basename:
        print 'Preset empty: %s' %preset
        LCD.print_lcd(0, 0, 'Preset Empty:  ' %preset)
        LCD.print_lcd(0, 1, '%s          '%preset)
        return
    print 'Preset loading: %s(%s)' %(preset, basename)
    LCD.print_lcd(0, 0, 'Preset loading:  ')
    LCD.print_lcd(0, 1, '%s          ' %preset)

    
    if preset == 'GZ_Basic':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'GZ Basic Layers_0%d_127.wav' %midinote)
            if os.path.isfile(file):
##                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'GZ_Shake':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'GZ Shake_0%d_127.wav' %midinote)
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'Pipa_Basic':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'PiPa Basic Layer_0%d_127.wav' %midinote )
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'Pipa_Fanyin':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'PiPa FanYin_0%d_127.wav' %midinote)
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'Pipa_Roll':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'PiPa Roll_0%d.wav' %midinote)
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'Xiao':
        for midinote in range(0, 127):
            file = os.path.join(dirname, '01 Xiao Trem_0%d.wav' %midinote)
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'Sheng':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'ChineeSheng_0%d_127.wav' %midinote)
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'ErHu_Basic':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'Erhu 000 Basic Layer_0%d_127.wav' %midinote)
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'ErHu_Legato':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'Erhu 001 Legato1_0%d_127.wav' %midinote)
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'ErHu_Pizz':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'Erhu 018 Pizz_0%d_115.wav' %midinote)
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    elif preset == 'ErHu_Thrill':
        for midinote in range(0, 127):
            file = os.path.join(dirname, 'Erhu 012 Trill1_0%d_115.wav' %midinote)
            if os.path.isfile(file):
                print file
                samples[midinote] = Sound(file, midinote)
    else:
        print 'Loading Error'


##    print samples.keys()
##    print samples.keys()[0]
    initial_keys = set(samples.keys())
    for midinote in xrange(128):
        if midinote > samples.keys()[0]:
            if midinote not in initial_keys:        
                samples[midinote] = samples[midinote-1]

    print 'Preset loaded: %s' %preset
    print
    LCD.print_lcd(0, 0, 'Preset loaded:   ')
    LCD.print_lcd(0, 1, '%s          ' %preset)


##OPEN LCD
LCD.init_lcd()
LCD.print_lcd(0, 0, 'Starting......')
LCD.turn_light(1)


##OPEN AUDIO DEVICE
				
p = pyaudio.PyAudio()

for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['maxOutputChannels'] > 0:
            print str(i) + ' -- ' + dev['name']
            if 'USB' in dev['name']:
                print dev['name']
                DEVICE_ID = i
           

try:
    stream = p.open(format = pyaudio.paInt16,
                    channels = 2,
                    rate = 44100,
                    output = True,
                    output_device_index = DEVICE_ID,
                    stream_callback = AudioCallback)
    print 'Opened Audio: ' + p.get_device_info_by_index(DEVICE_ID)['name']
except:
    print 'Invalid Audio Device ID'
    print 'Here is a list of audio devices:'
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['maxOutputChannels'] > 0:
            print str(i) + ' -- ' + dev['name']
    exit(1)


presets = ('GZ_Basic', 'GZ_Shake', 'Pipa_Basic', 'Pipa_Fanyin', 'Pipa_Roll',
           'Xiao', 'ErHu_Basic', 'ErHu_Legato', 'ErHu_Pizz', 'ErHu_Thrill',
           'Sheng')
preset = presets[0]
currentpreset = 0
LoadSamples()


##Button

button1 = Button(4)
button2 = Button(23)

def Previous():
    global preset, currentpreset
    if currentpreset == 0:
        currentpreset = 10
    else:
        currentpreset -= 1
    preset = presets[currentpreset]
    LoadSamples()

def Next():
    global preset, currentpreset
    if currentpreset == 10:
        currentpreset = 0
    else:
        currentpreset += 1
    preset = presets[currentpreset]
    LoadSamples()

def Buttons():
    button1.when_pressed = Previous
    button2.when_pressed = Next

    pause()

ButtonThread = threading.Thread(target = Buttons)
ButtonThread.daemon = True
ButtonThread.start()

##MIDI DEVICES DETECTION
##MAIN LOOP

midi_in = rtmidi.MidiIn()
midi_in.callback = MidiCallback
for port in midi_in.ports:
    if 'Midi Through' not in port:
        midi_in.open_port(port)
        print 'Opened MIDI: ' + port
    
while True:
    time.sleep(2)
