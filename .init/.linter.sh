#!/bin/bash
cd /home/kavia/workspace/code-generation/Subtitle_Sync_Platform/FrontendWebDashboard
npm run build
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
   exit 1
fi

