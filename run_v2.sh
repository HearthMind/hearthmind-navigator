#!/bin/bash
# Kill any existing navigator on 5000
pkill -f "app_v2.py" 2>/dev/null
sleep 1
cd /home/hyperion/hearthmind/navigator
source .env
export GEMINI_API_KEY
python3 src/app_v2.py
