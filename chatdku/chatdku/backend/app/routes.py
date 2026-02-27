from flask import request, jsonify, session, g
from ollama import ChatResponse
import requests
from flask_socketio import emit
from app.models import Feedback, Request, UploadedFile, UserModel
from chatdku.core.agent import Agent
from flask import Response, stream_with_context
from dotenv import load_dotenv
import os
from datetime import datetime, timezone, date
from werkzeug.utils import secure_filename
import uuid
from app.utils import shib_attrs, allowed_file, ALLOWED_EXTENSIONS

load_dotenv()


def routes(app, db, socketio, logger):
    WHISPER_MODEL_URI = os.getenv("WHISPER_MODEL_URI")

    @app.before_request
    def fill_session():
        attrs = shib_attrs()
        if attrs["eppn"]:  # only if user is logged in
            session["user"] = attrs
            netid = attrs["eppn"].split("@")[0]
            # g.user = db.session.scalar(
            #     db.select(UserModel).where(UserModel.netid == netid)
            # )

            # if not g.user:
            #     # g.user = UserModel(netid=netid)
            #     db.session.add(g.user)
            #     db.session.commit()  # Commented because the db schema wasn't created yet

    @app.after_request
    def no_sniff_header(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def user_check():
        if not hasattr(g, "user"):
            return jsonify({"message": "Unauthorized"}), 401

    @app.route("/user")
    def user_info():
        attrs = shib_attrs()
        if not attrs["eppn"]:
            return jsonify({"error": "unauthenticated"}), 401
        return jsonify(attrs)

    @app.route("/chat", methods=["POST"])
    def chat():
        # req = Request(date_=datetime.now(timezone.utc), req_count=1)
        # db.session.add(req)
        # db.session.commit()
        messages = request.json.get("messages", [])
        question_id = request.json["chatHistoryId"]
        mode = "default"
        max_iteration = 2 if mode == "agent" else 1
        if not messages:
            return {"error": "No message provided"}, 400

        try:
            message_content = messages[-1]["content"]

            # Create a new Agent instance per request
            agent = Agent(
                max_iterations=max_iteration, streaming=False, get_intermediate=False
            )
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

    @app.route("/feedback", methods=["POST"])
    def save_feedback():
        try:
            data = request.get_json()
            user_input = data["userInput"]
            bot_answer = data["botAnswer"]
            feedback_reason = data["feedbackReason"]
            question_id = data["chatHistoryId"]
            time = datetime.now(timezone.utc)
            feedback = Feedback(
                user_input=user_input,
                bot_answer=bot_answer,
                feedback_reason=feedback_reason,
                question_id=question_id,
                time=time,
            )
            db.session.add(feedback)
            db.session.commit()
            print("data recorded")
            return jsonify({"message": "Feedback saved successfully"})
        except Exception as e:
            return jsonify({"message": str(e)})

    @app.route("/upload", methods=["POST"])
    def upload():
        user_check()
        if "file" not in request.files:
            return jsonify({"message": "Files required"})
        data = request.files.get("file")
        if not data or data.filename == "":
            return jsonify({"message": "No file received"})

        if not allowed_file(data.filename):
            return jsonify({"message": "Only PDF files are allowed"})

        filename = f"{secure_filename(g.user.netid)}_{uuid.uuid4()}.pdf"
        folder_path = os.getenv("UPLOAD_PATH", "./data/uploads")
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        filepath = os.path.join(folder_path, filename)
        data.save(filepath)

        uploaded_file = UploadedFile(file_name=filename)
        db.session.add(uploaded_file)
        db.session.commit()
