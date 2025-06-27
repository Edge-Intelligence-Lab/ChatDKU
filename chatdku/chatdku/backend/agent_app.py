#!/usr/bin/env python3
# FIXME: Purge API key from the history of this file

### TODO: Create multiple app objects in advance, lock the app object for each user, and reset the app object when the user is not using it.

from flask import Flask, request
from flask_cors import CORS
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from flask import Response, stream_with_context, jsonify, session
from flask import request
from models import Feedback
import dspy

from chatdku.setup import setup, use_phoenix
from chatdku.core.agent import Agent,CustomClient
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
app.secret_key = "CHANGE-ME-TO-A-RANDOM-STRING"
CORS(app)

db=SQLAlchemy()
app.config["SQLALCHEMY_DATABASE_URI"]="sqlite:///./database.db"

db.init_app(app)

def shib_attrs():
    """Pull attributes added by Apache ↔︎ Shibboleth."""
    return {
        "eppn":        request.headers.get("X-EPPN"),         # e.g. jbd123@duke.edu
        "displayName": request.headers.get("X-DisplayName"),  # e.g. Jane BlueDevil
    }

@app.before_request
def fill_session():
    attrs = shib_attrs()
    if attrs["eppn"]:                 # only if user is logged in
        session["user"] = attrs       # now available everywhere in Flask

@app.route("/api/user")
def user_info():
    attrs = shib_attrs()
    if not attrs["eppn"]:
        return jsonify({"error": "unauthenticated"}), 401
    return jsonify(attrs)

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



@app.route('/save_feedback', methods=['POST'])
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
        return jsonify({'message': 'Feedback saved successfully'})
    except Exception as e:
        return jsonify({"message":str(e)})



if __name__ == "__main__":
    setup()
    use_phoenix()
    llama_client = CustomClient()
    dspy.settings.configure(lm=llama_client)
    agent = Agent(max_iterations=1, streaming=True, get_intermediate=False)

    # NOTE: Might want to make it easier to change the port
    app.run(host="0.0.0.0", port=18420)
