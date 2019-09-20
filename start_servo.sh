#!/bin/bash

sudo killall -9 python3

sudo killall -9 pigpiod
sudo rm /var/run/pigpio.pid
sudo pigpiod

python3 /home/pi/github/DoorKeyPi/main.py
