#!/bin/bash
cd /home/hyperion/hearthmind/navigator
python3 src/app_v2.py &
echo $! > /tmp/nav_v2.pid
sleep 4
echo "=== /api/programs?q=disability ==="
curl -s "http://localhost:5000/api/programs?q=disability&limit=3"
echo ""
echo "=== /api/categories ==="
curl -s "http://localhost:5000/api/categories"
