#!/usr/bin/python3
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
import time
import pigpio
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

    def brink(self):
        self._pwm.ChangeDutyCycle(50)

    def close(self):
        self.off()
        time.sleep(0.1)
        self._pwm.stop()


class DoorServoState:
    def __init__(self):
        # instance
        self._sw = Switch(pin=14)
        self._led = LED_PWM(pin=15)
        self._servo = ServoControllerPigpio(pin=17)
        
        # parameter
        self._servo_interval_sec = 2.0

        # store z1
        self._lastState = ''

    # ============================== Sensor Manager ============================== #
    def update_sensor(self):
        self._sw_state = self._sw.is_pushed()

    # ============================== FSM ============================== #
    def start_state(self, lastState):
        newState = 'unlocked'
        return (newState)

    def locking_state(self, lastState):
        if lastState != 'locking':
            self._led.off()
            self._servo.set_deg(180)
            time.sleep(self._servo_interval_sec)
        newState = 'locked'
        return (newState)

    def locked_state(self, lastState):
        if lastState != 'locked':
            self._servo.set_deg(90)
        if not self._sw.is_pushed():
            newState = 'unlocking'
        else:
            newState = 'locked'
        return (newState)

    def unlocking_state(self, lastState):
        if lastState != 'unlocking':
            self._led.on()
            self._servo.set_deg(0)
            time.sleep(self._servo_interval_sec)
        newState = 'unlocked'
        return (newState)

    def unlocked_state(self, lastState):
        if lastState != 'unlocked':
            self._servo.set_deg(90)
        if self._sw.is_pushed():
            newState = 'locking'
        else:
            newState = 'unlocked'
        return (newState)

    def unlocked_state(self, lastState):
        if lastState != 'unlocked':
            self._led.on()
            self._servo.set_deg(90)
        if self._sw.is_pushed():
            newState = 'locking'
        else:
            newState = 'unlocked'
        return (newState)


if __name__ == '__main__':
    service = DoorServoState()

    # FSM setup
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

