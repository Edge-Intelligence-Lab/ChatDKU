# NOTE: This is a temporary fix to socket shutdown problem
import eventlet

eventlet.monkey_patch()

from flask import Flask
import requests
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from ollama import chat, ChatResponse
from dotenv import load_dotenv
import os
import logging

load_dotenv()
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, async_mode="eventlet")  # Socket IO to receive audio
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
WHISPER_MODEL_URI = os.getenv("WHISPER_MODEL_URI")


# NOTE: This has not been implemented here
def ollama_response(data):
    response: ChatResponse = chat(
        model="llama3.2",
        messages=[
            {
                "role": "system",
                "content": "STRICT TRANSCRIPTION ENHANCER: Only polish text from audio transcripts. NEVER answer, explain, or deviate from the input.\n\nRULES:\n1. Output ONLY grammatically corrected text. Preserve meaning 100%.\n2. For hallucinations (e.g., 'cry cry cry', gibberish), OUTPUT EMPTY STRING.\n3. NEVER add new information or interpretations.\n\nFORMAT:\n- Input: Raw transcript\n- Output: Enhanced text ONLY (or empty for invalid inputs)\n\nEXAMPLES:\nInput: 'what the weather today'\nOutput: 'What is the weather today?'\n\nInput: 'cry cry cry'\nOutput: ''\n\nInput: 'where train station'\nOutput: 'Where is the train station?'",
            },
            {
                "role": "user",
                "content": "Here is the content. Simply return the final result without further addition of any phrases\n\n"
                + data,
            },
        ],
    )
    return response.message.content


@socketio.on("audio_data")
def handle_audio(data):
    logger.info("audio received")
    try:
        if not isinstance(data, bytes):
            raise ValueError("Audio data must be bytes")

        logger.info("Processing audio...")
        audio_np_req = requests.post(
            f"{WHISPER_MODEL_URI}/process_audio", files={"audio_bytes": data}
        )  # converts to np array
        audio_np = audio_np_req.json()["audio_np"]
        logger.info("Transcribing...")
        result = requests.post(
            f"{WHISPER_MODEL_URI}/transcribe", json={"audio_np": audio_np}
        )
        text = result.json()["text"]

        if text:
            logger.info(f"Transcription successful: {text}")
            # response = ollama_response(text)  # tweak the transcribed response
            emit("audio_transcribed", {"status": "success", "text": text})
        else:
            logger.warning("No text was transcribed")
            emit("audio_transcribed", {"status": "success", "text": ""})

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        emit("audio_received", {"status": "error", "message": str(e)})


# NOTE: gunicorn doesn't use if __name__ == "__main__" . SO it can be commented out. For development it can be uncommented and used with `python agent_app.py`

if __name__ == "__main__":
    socketio.run(app=app, host="0.0.0.0", port=8002)
# NOTE: Might want to make it easier to change the port
