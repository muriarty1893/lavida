#!/bin/bash

sleep 5
source main_env/bin/activate
cd /home/murat/Desktop/lavida
python main.py > startup_log.txt 2>&1