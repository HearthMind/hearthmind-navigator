#!/bin/bash
cd /home/hyperion/hearthmind/navigator
source .env

# Kill any existing instance
pkill -f app_v2.py 2>/dev/null
sleep 1

# Start Navigator v2
python3 src/app_v2.py > /tmp/nav_v2.log 2>&1 &
sleep 4

# Test chat endpoint
curl -s -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need help paying my electric bill", "history": []}'
