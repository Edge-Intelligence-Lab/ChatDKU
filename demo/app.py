#!/usr/bin/env python3
# FIXME: Purge API key from the history of this file

from flask import Flask, request
from flask_cors import CORS

import os
import sys

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../RAG"))
)
from query import get_pipeline
from settings import setup, use_phoenix

app = Flask(__name__)
CORS(app)


@app.route("/chat", methods=["POST"])
def chat():
    """
    Return response stream from query pipeline given JSON formatted chat history as input.

    The response is a text stream on success, but a JSON object with error message on failure.
    """
    # example data :
    # {'messages': [{'role': 'user', 'content': 'Hello'}, {'role': 'assistant', 'content': 'Hey there! How can I assist you today? 😊'}, {'role': 'user', 'content': 'What do you know about DKU?'}]}

    messages = request.json["messages"]
    if not messages:
        return {"error": "No message provided"}, 400

    try:
        # TODO: Support conversation instead of only responding to the last message
        stream = pipeline.run(input=messages[-1]["content"])
        return stream.response_gen, 200
    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":
    setup()
    use_phoenix()
    pipeline = get_pipeline()
    # NOTE: Might want to make it easier to change the port
    app.run(host="0.0.0.0", port=5000)

