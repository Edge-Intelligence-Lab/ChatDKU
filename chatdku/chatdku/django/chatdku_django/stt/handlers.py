import logging
import os
import requests
from .socketio_server import sio

logger = logging.getLogger(__name__)
WHISPER_MODEL_URI = os.getenv("WHISPER_MODEL_URI")


@sio.on('audio_data')
async def handle_audio(sid, data):
    """处理音频数据并返回转录文本"""
    logger.info("Audio received from client")
    try:
        if not isinstance(data, bytes):
            raise ValueError("Audio data must be bytes")

        logger.info("Processing audio...")
        audio_np_req = requests.post(
            f"{WHISPER_MODEL_URI}/process_audio",
            files={"audio_bytes": data}
        )
        audio_np = audio_np_req.json()["audio_np"]

        logger.info("Transcribing...")
        result = requests.post(
            f"{WHISPER_MODEL_URI}/transcribe",
            json={"audio_np": audio_np}
        )
        text = result.json()["text"]

        if text:
            logger.info(f"Transcription successful: {text}")
            await sio.emit("audio_transcribed", {"status": "success", "text": text}, room=sid)
        else:
            logger.warning("No text was transcribed")
            await sio.emit("audio_transcribed", {"status": "success", "text": ""}, room=sid)

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        await sio.emit("audio_received", {"status": "error", "message": str(e)}, room=sid)
