from flask import request,jsonify
import io
import torch
import whisper
from pydub import AudioSegment
import tempfile
import os
import gc
from ollama import chat, ChatResponse
from flask_socketio import emit
from models import Feedback
from chatdku.core.agent import Agent
from flask import Response, stream_with_context


def routes(app,db,socketio,logger,model):
    @app.route("/reset", methods=["POST"])
    def reset_agent():
        return {
            "good": "Chat history is not supported by the backend yet. No agent has been reset for now."
        }, 200


    @app.route("/chat", methods=["POST"])
    def chat():
        messages = request.json.get("messages", [])
        question_id = request.json["chatHistoryId"]
        mode=request.json.get("mode","default")
        max_iteration=10 if mode=="agent" else 1
        if not messages:
            return {"error": "No message provided"}, 400

        try:
            message_content = messages[-1]["content"]

            # Create a new Agent instance per request
            agent = Agent(max_iterations=max_iteration, streaming=True, get_intermediate=False)
            responses_gen = agent(
                current_user_message=message_content, question_id=question_id
            )

            # Stream the responses
            def generate():
                for response in responses_gen.response:
                    yield f"{response}"

            return Response(stream_with_context(generate()), content_type="text/plain")

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    #NOTE: This has not been implemented here
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


    def process_audio(audio_bytes):
        temp_path = None
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                temp_path = temp_wav.name

                # Load WebM audio and convert to WAV
                audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="webm")
                audio = audio.set_frame_rate(16000).set_channels(
                    1
                )  # set config based on whisper compatiability (mono with 16khz)
                audio.export(temp_path, format="wav")

            audio_np = whisper.load_audio(temp_path)

            return audio_np
        except Exception as e:
            logger.error(f"Audio processing error: {str(e)}")
            raise
        finally:
            # ensure cleanup happens even after error occurs
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)  # delete the file from the system
                    gc.collect()  # forche the garbage collector to run and cleanup
                except Exception as e:
                    logger.warning(f"Could not delete temp file {temp_path}: {str(e)}")


    @socketio.on("audio_data")
    def handle_audio(data):
        try:
            if not isinstance(data, bytes):
                raise ValueError("Audio data must be bytes")

            logger.info("Processing audio...")
            audio_np = process_audio(data)  # converts to np array

            logger.info("Transcribing...")
            result = model.transcribe(audio_np)
            text = result.get("text", "").strip()

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

    @app.route('/save-feedback', methods=['POST'])
    def save_feedback():
        try:
            data = request.get_json()
            user_input = data['userInput']
            bot_answer = data['botAnswer']
            feedback_reason = data['feedbackReason']
            question_id = data['chatHistoryId']

            feedback=Feedback(user_input=user_input,bot_answer=bot_answer,feedback_reason=feedback_reason,question_id=question_id)
            db.session.add(feedback)
            db.session.commit()
            print("data recorded")
            return jsonify({'message': 'Feedback saved successfully'})
        except Exception as e:
            return jsonify({"message":str(e)})