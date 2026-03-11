#!/bin/bash
# Quick chat test
source /home/hyperion/hearthmind/navigator/.env
export GEMINI_API_KEY
pkill -f "app_v2.py" 2>/dev/null
sleep 1
cd /home/hyperion/hearthmind/navigator
python3 src/app_v2.py &
sleep 4
echo "=== Chat test ==="
curl -s -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"I have PTSD and need help paying rent. What programs exist for me?","history":[]}'
