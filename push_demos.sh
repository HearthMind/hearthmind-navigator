#!/bin/bash
cd /home/hyperion/hearthmind/navigator
git add templates/navigator_sw.html templates/navigator_client.html src/routes_v2.py
git commit -m "Add SW professional face (/pro) and client app (/app) demo pages"
git push origin main
