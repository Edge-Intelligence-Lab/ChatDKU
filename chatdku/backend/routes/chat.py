from fastapi import HTTPException, Query, APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
from chatdku.backend.tools import get_tools
from chatdku.core.agent import Agent
from typing import List
import uuid
from redis import Redis
import os
import dotenv

dotenv.load_dotenv()

router=APIRouter()
redis_password = os.getenv("REDIS_PASSWORD")
redis_host = os.getenv("REDIS_HOST")

# set up redis
redis_client = Redis(
    host=redis_host, port=6379, username="default", password=redis_password, db=0
)

class ChatRequest(BaseModel):
    current_user_message: str
    previous_conversation: List[tuple]
    max_iteration:int
    question_id:uuid.UUID
    id:uuid.UUID
    user_id:str
    search_mode:int
    docs:List[str]


@router.post("/chat")
def chat(data:ChatRequest,bg: BackgroundTasks):
    tools=get_tools(user_id=data.user_id,search_mode=data.search_mode,docs=data.docs)
    channel = f"chat:{data.id}"
    agent=Agent(
        max_iterations=data.max_iteration,
        previous_conversation=data.previous_conversation,
        tools=tools
    )
    responses_gen = agent(
            current_user_message=data.current_user_message,
            question_id=data.question_id,
        )
    
    def generate():
        try:
            buffer = ""
            CHUNK_SIZE = 100

            for response in responses_gen.response:
                buffer += response

                while len(buffer) >= CHUNK_SIZE:
                    chunk = buffer[:CHUNK_SIZE]
                    buffer = buffer[CHUNK_SIZE:]

                    redis_client.xadd(channel, {
                        "type": "token",
                        "content": chunk
                    }, maxlen=100000)

            # flush remaining
            if buffer:
                redis_client.xadd(channel, {
                    "type": "token",
                    "content": buffer
                }, maxlen=100000)

            redis_client.xadd(channel, {"type": "end"})
            redis_client.expire(channel, 300)

        except Exception as e:
            redis_client.xadd(channel, {
                "type": "error",
                "message": str(e)
            })

    bg.add_task(generate)

    return {"status": "started"}






