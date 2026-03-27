
import eventlet
import eventlet.wsgi
import ssl
from flask import Flask, request
import requests
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import os
import logging

# Load environment
load_dotenv()

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")  # Socket.IO to receive audio

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
WHISPER_MODEL_URI = os.getenv("WHISPER_MODEL_URI")

@socketio.on("audio_data")
def handle_audio(data):
    logger.info("audio received")
    try:
        if not isinstance(data, bytes):
            raise ValueError("Audio data must be bytes")

        logger.info("Processing audio...")
        audio_np_req = requests.post(
            f"{WHISPER_MODEL_URI}/process_audio", files={"audio_bytes": data}
        )
        audio_np = audio_np_req.json()["audio_np"]

        logger.info("Transcribing...")
        result = requests.post(
            f"{WHISPER_MODEL_URI}/transcribe", json={"audio_np": audio_np}
        )
        text = result.json()["text"]

        if text:
            logger.info(f"Transcription successful: {text}")
            emit("audio_transcribed", {"status": "success", "text": text})
        else:
            logger.warning("No text was transcribed")
            emit("audio_transcribed", {"status": "success", "text": ""})

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        emit("audio_received", {"status": "error", "message": str(e)})






if __name__ == "__main__":
    
    cert_file = '/etc/ssl/certs/chatdku.dukekunshan.edu.cn.pem'
    key_file = '/etc/ssl/updated_certs/chatdku.dukekunshan.edu.cn.key'
    ssl_args = {
        'certfile': cert_file,
        'keyfile': key_file,
        'server_side': True,
        'ssl_version': ssl.PROTOCOL_TLS_SERVER,
    }

     #Create raw socket
    sock = eventlet.listen(('0.0.0.0', 8007))
    wrapped_socket = eventlet.wrap_ssl(sock, **ssl_args)

    logger.info("Running secure Socket.IO server on http://0.0.0.0:8007")
    eventlet.wsgi.server(wrapped_socket, app)
    #socketio.run(app, host="0.0.0.0", port=8007)
