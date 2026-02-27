
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
STT_HOST = os.getenv("STT_HOST", "0.0.0.0")
STT_PORT = int(os.getenv("STT_PORT", "8007"))
SSL_CERT_FILE = os.getenv("SSL_CERT_FILE")
SSL_KEY_FILE = os.getenv("SSL_KEY_FILE")

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
    if SSL_CERT_FILE and SSL_KEY_FILE:
        ssl_args = {
            "certfile": SSL_CERT_FILE,
            "keyfile": SSL_KEY_FILE,
            "server_side": True,
            "ssl_version": ssl.PROTOCOL_TLS_SERVER,
        }

        sock = eventlet.listen((STT_HOST, STT_PORT))
        wrapped_socket = eventlet.wrap_ssl(sock, **ssl_args)

        logger.info(
            "Running secure Socket.IO server on https://%s:%s", STT_HOST, STT_PORT
        )
        eventlet.wsgi.server(wrapped_socket, app)
    else:
        logger.info(
            "Running Socket.IO server on http://%s:%s", STT_HOST, STT_PORT
        )
        socketio.run(app, host=STT_HOST, port=STT_PORT)
