#!/usr/bin/env python3
# FIXME: Purge API key from the history of this file

### TODO: Create multiple app objects in advance, lock the app object for each user, and reset the app object when the user is not using it.

from flask import Flask, request
from flask_cors import CORS
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from flask import Response, stream_with_context, jsonify

import dspy

from chatdku.setup import setup, use_phoenix
from chatdku.core.agent import Agent,CustomClient

app = Flask(__name__)
CORS(app)

@app.route("/reset",methods=["POST"])
def reset_agent():
    agent.reset()
    return {"good": "Agent has been reset."}, 200

@app.route("/chat", methods=["POST"])
def chat():
    """
    Return response stream from query pipeline given JSON formatted chat history as input.

    The response is a text stream on success, but a JSON object with error message on failure.
    """
    # example data :
    # {'messages': [{'role': 'user', 'content': 'Hello'}, {'role': 'assistant', 'content': 'Hey there! How can I assist you today? 😊'}, {'role': 'user', 'content': 'What do you know about DKU?'}]}

    messages = request.json["messages"]
    question_id = request.json["chatHistoryId"]
    print("1"*100)
    print(question_id)
    if not messages:
        return {"error": "No message provided"}, 400

    try:
        print(messages[0]["content"])
        messages = messages[-1]["content"]
        responses_gen = agent(current_user_message=messages, question_id=question_id)
    # 使用 Flask 的 Response 对象和 stream_with_context 进行流式输出
        def generate():
            for response in responses_gen.response:
                yield f"{response}"  # 每个响应后加换行符
            # for i,r in enumerate(responses_gen):
            #     for response in r.response:
            #         yield f"{response}"  # 每个响应后加换行符

        return Response(stream_with_context(generate()), content_type='text/plain')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    setup()
    use_phoenix()
    llama_client = CustomClient()
    dspy.settings.configure(lm=llama_client)
    agent = Agent(max_iterations=2, streaming=True, get_intermediate=False)

    # NOTE: Might want to make it easier to change the port
    app.run(host="0.0.0.0", port=9012)

