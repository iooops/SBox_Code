##import RPi.GPIO as GPIO
##import time
##import os
##
##GPIO.setmode(GPIO.BOARD)
##GPIO.setup(22, GPIO.IN)
##while True:
##    if(GPIO.input(22)):
##        print 'haha'
##        #os.system("sudo shutdown -h now")
##        break
##time.sleep(1)

from gpiozero import Button
from signal import pause
import os

def shutdown():
    os.system('sudo shutdown -h now')
    print 'shutdown'

button = Button(25)
button.when_pressed = shutdown

pause()
