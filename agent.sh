#!/usr/bin/env bash

set -e

PORT=8123
HOST=0.0.0.0
WORKERS=${WORKERS:-4}


#port check
if lsof -i :$PORT >/dev/null 2>&1; then
    echo "PORT :$PORT already in use..."
    exit 1
fi


#start the agent
source .venv/bin/activate

echo "Starting FastAPI app..."
echo "Host: $HOST, Port: $PORT, Workers: $WORKERS"

# Run Gunicorn with Uvicorn workers
nohup  python -m gunicorn \
    -w $WORKERS \
    -k uvicorn.workers.UvicornWorker \
    chatdku.backend.main:app \
    --bind $HOST:$PORT \
    --log-level info &
 
