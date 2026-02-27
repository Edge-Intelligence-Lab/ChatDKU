#!/bin/bash

# Check if the port number is passed as an argument
if [ -z "$1" ]; then
  echo "Usage: $0 <port> [content]"
  exit 1
fi

PORT=$1
CONTENT=${2:-"What do you know about DKU?"} # Default to "What do you know about DKU?" if no second argument is provided

# Curl command using the specified port and content
curl --header 'Content-Type: application/json' \
  --header 'Connection: close' \
  --data "{\"messages\": [{\"role\": \"user\", \"content\": \"$CONTENT\"}], \"chatHistoryId\": \"1731747599701-p8jcj69307\"}" \
  -v \
  http://localhost:$PORT/chat
