#!/usr/bin/env python3
# TODO: Support chat history

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import dspy

from chatdku.setup import setup, use_phoenix
from chatdku.core.agent import Agent, CustomClient

app = Flask(__name__)
CORS(app)

setup()
use_phoenix()
llama_client = CustomClient()
dspy.settings.configure(lm=llama_client)


@app.route("/reset", methods=["POST"])
def reset_agent():
    return {
        "good": "Chat history is not supported by the backend yet. No agent has been reset for now."
    }, 200


@app.route("/chat", methods=["POST"])
def chat():
    messages = request.json.get("messages", [])
    question_id = request.json["chatHistoryId"]
    if not messages:
        return {"error": "No message provided"}, 400

    try:
        message_content = messages[-1]["content"]

        # Create a new Agent instance per request
        agent = Agent(max_iterations=2, streaming=True, get_intermediate=False)
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
