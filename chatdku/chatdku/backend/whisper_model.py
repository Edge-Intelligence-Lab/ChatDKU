import torch
import whisper
from pydub import AudioSegment
import numpy as np
from flask import request, Flask, jsonify
import io
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")
model = whisper.load_model("base").to(device)

@app.route("/process_audio", methods=["POST"])
def process_audio():
    if "audio_bytes" not in request.files:
        return jsonify({"error": "Missing audio_bytes file"}), 400

    try:
        audio_file = request.files["audio_bytes"]
        audio_bytes = audio_file.read()
        
        # Convert WebM to WAV in-memory
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="webm")
        audio = audio.set_frame_rate(16000).set_channels(1)
        
        # Export to WAV in-memory
        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format="wav")
        wav_buffer.seek(0)
        
        # Load directly into numpy array
        audio_np = whisper.load_audio(wav_buffer)
        return jsonify({"audio_np": audio_np.tolist()})

    except Exception as e:
        logger.error(f"Audio processing error: {str(e)}")
        return jsonify({"error": "Audio processing failed"}), 500

@app.route("/transcribe", methods=["POST"])
def transcribe():
    if not request.json or "audio_np" not in request.json:
        return jsonify({"error": "Missing audio_np"}), 400

    try:
        # Convert list back to numpy array
        audio_np = np.array(request.json["audio_np"], dtype=np.float32)
        
        result = model.transcribe(audio_np)
        text = result.get("text", "").strip()
        return jsonify({"text": text})
    
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        return jsonify({"error": "Transcription failed"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)