#!/bin/bash

# Check if the port number is passed as an argument
if [ -z "$1" ]; then
  echo "Usage: $0 <port>"
  exit 1
fi

PORT=$1

# Curl command using the specified port
curl --header 'Content-Type: application/json' \
  --header 'Connection: close' \
  --data "{\"userInput\": \"the user input\", \"botAnswer\": \"the bot answer\", \"feedbackReason\": \"the feedback reason\", \"chatHistoryId\": \"1731747599701-p8jcj69307\"}" \
  -v \
  http://localhost:$PORT/save-feedback
