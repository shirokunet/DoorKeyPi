#!/usr/bin/python3
# -*- coding: utf-8 -*-

import binascii
import nfc
import pigpio
import RPi.GPIO as GPIO
import time
import yaml
from statemachine import StateMachine


class ServoControllerPigpio():
    def __init__(self, pin=18, frequency=50, limit_angle_f=180.0, limit_angle_r=0.0):
        self._pin = pin
        self._frequency = frequency
        self._limit_angle_f = limit_angle_f
        self._limit_angle_r = limit_angle_r

        self._servo = pigpio.pi()

    def _limit_deg(self, deg):
        if deg > self._limit_angle_f:
            return self._limit_angle_f
        elif deg < self._limit_angle_r:
            return self._limit_angle_r
        else:
            return deg

    def _deg_to_percentage(self, deg):
        return (12 - 2.5) / 180 * deg + 2.5

    def _percentage_to_microsec(self, percentage):
        return 1.0 / self._frequency * 1000000 * (percentage / 100)

    def set_deg(self, deg):
        limited_deg = self._limit_deg(deg)
        percentage = self._deg_to_percentage(limited_deg)
        microsec = self._percentage_to_microsec(percentage)
        self._servo.set_servo_pulsewidth(self._pin, microsec)

    def close(self):
        return


class Switch():
    def __init__(self, pin=None):
        self._pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)

    def is_pushed(self):
        if GPIO.input(self._pin) == GPIO.LOW:
            return True
        else:
            return False


class LED_PWM():
    def __init__(self, pin=None, freq=1.5):
        self._pin = pin
        self._freq = freq

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._pin, GPIO.OUT)

        self._pwm = GPIO.PWM(self._pin, self._freq)
        self._pwm.start(0)

    def on(self):
        self._pwm.ChangeDutyCycle(100)

    def off(self):
        self._pwm.ChangeDutyCycle(0)

    def blink(self):
        self._pwm.ChangeDutyCycle(50)

    def close(self):
        self.off()
        time.sleep(0.1)
        self._pwm.stop()


class CompareNfcIdm:
    def __init__(self):
        self._suica = nfc.clf.RemoteTarget("212F")
        self._suica.sensf_req = bytearray.fromhex("0000030000")
        self._clf = nfc.ContactlessFrontend("usb")
    
    def is_in_list(self, idm_list):
        target = self._clf.sense(self._suica,iterations=3,interval=1.0)
        if target:
            tag = nfc.tag.activate(self._clf,target)
            tag.sys = 3
            received_idm = binascii.hexlify(tag.idm)

            for listed_idm in idm_list:
                if listed_idm == received_idm.decode():
                    return True
        return False

class DoorServoState:
    def __init__(self, cfg):
        # instance
        self._nfc = CompareNfcIdm()
        self._sw = Switch(pin=14)
        self._led = LED_PWM(pin=15)
        self._servo = ServoControllerPigpio(pin=17)
        
        # parameter
        self._idm_list = cfg['family_idm']
        self._servo_interval_sec = 2.0

        # store z1
        self._lastState = ''
        self._sw_counter = 0

    # ============================== Sensor Manager ============================== #
    def update_sensor(self):
        self._sw_pushed = self._sw.is_pushed()
        self._nfc_matched = self._nfc.is_in_list(self._idm_list)

    # ============================== FSM ============================== #
    def start_state(self, lastState):
        newState = 'unlocked'
        return (newState)

    def locking_state(self, lastState):
        if lastState != 'locking':
            self._led.on()
            self._servo.set_deg(180)
            time.sleep(self._servo_interval_sec)
        newState = 'locking'

        if not self._nfc_matched:
            newState = 'locked'

        return (newState)

    def locked_state(self, lastState):
        if lastState != 'locked':
            self._led.off()
            self._servo.set_deg(90)
        newState = 'locked'

        if not self._sw_pushed:
            self._sw_counter += 1
    
        if self._sw_counter > 50 or self._nfc_matched:
            self._sw_counter = 0
            newState = 'unlocking'

        return (newState)

    def unlocking_state(self, lastState):
        if lastState != 'unlocking':
            self._led.on()
            self._servo.set_deg(0)
            time.sleep(self._servo_interval_sec)
        newState = 'unlocking'

        if not self._nfc_matched:
            newState = 'unlocked'

        return (newState)

    def unlocked_state(self, lastState):
        if lastState != 'unlocked':
            self._led.blink()
            self._servo.set_deg(90)
        newState = 'unlocked'

        if self._sw_pushed:
            self._sw_counter += 1
    
        if self._sw_counter > 50 or self._nfc_matched:
            self._sw_counter = 0
            newState = 'locking'

        return (newState)


if __name__ == '__main__':
    # get yaml config file
    ymlfile = open('config.yml')
    cfg = yaml.load(ymlfile, Loader=yaml.SafeLoader)
    ymlfile.close()

    # FSM setup
    service = DoorServoState(cfg)
    m = StateMachine()

    m.add_state('start', service.start_state)
    m.add_state('locking', service.locking_state)
    m.add_state('locked', service.locked_state)
    m.add_state('unlocking', service.unlocking_state)
    m.add_state('unlocked', service.unlocked_state)
    m.add_state('end', None, end_state=1)

    m.set_start('start')
    m.setup_run()

    # FSM loop
    handler = m.handlers[m.startState]
    lastState = 'start'
    currentState = 'start'

    try:
        while True:
            # update sensor
            service.update_sensor()

            # change state
            (newState) = handler(lastState)
            handler = m.handlers[newState.upper()]

            if lastState != currentState:
                print(lastState, '>>', currentState)
            lastState = currentState
            currentState = newState

            time.sleep(0.01)

    except KeyboardInterrupt:
        GPIO.cleanup()
