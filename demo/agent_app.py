#!/usr/bin/env python3

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import asyncio
import dspy
import os
import sys

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../RAG"))
)
from setup import setup, use_phoenix

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../agent_dku"))
)
from agent import Agent, CustomClient

app = Flask(__name__)
CORS(app)

# 全局初始化
setup()
use_phoenix()
llama_client = CustomClient()
dspy.settings.configure(lm=llama_client)

@app.route("/reset", methods=["POST"])
def reset_agent():
    agent = Agent(max_iterations=5, streaming=True, get_intermediate=True)
    agent.reset()
    return {"good": "Agent has been reset."}, 200

from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor()

@app.route("/chat", methods=["POST"])
async def chat():
    messages = request.json.get("messages", [])
    if not messages:
        return {"error": "No message provided"}, 400

    try:
        message_content = messages[-1]["content"]

        # 在线程池中运行Agent
        loop = asyncio.get_event_loop()
        agent = Agent(max_iterations=5, streaming=True, get_intermediate=True)
        responses_gen = await loop.run_in_executor(
            executor, agent, message_content
        )

        async def generate():
            for r in responses_gen:
                for response in r.response:
                    yield f"{response}"
                    await asyncio.sleep(0)

        return Response(stream_with_context(generate()), content_type='text/plain')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, threaded=True)
