from fastapi import HTTPException, Query, APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
from chatdku.backend.tools import get_tools
from chatdku.core.agent import Agent
from chatdku.core.intermediate_tracing import EventStream

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
def chat(data: ChatRequest, bg: BackgroundTasks):

    tools = get_tools(
        user_id=data.user_id,
        search_mode=data.search_mode,
        docs=data.docs
    )

    channel = f"chat:{data.id}"

    def send(events):
        redis_client.xadd(
            channel,
            {
                "type": events["type"],
                "payload": json.dumps(events)
            },            
            maxlen=100000
        )

    stream = EventStream(send)

    def generate():
        try:
            agent = Agent(
                stream,
                max_iterations=data.max_iteration,
                previous_conversation=data.previous_conversation,
                tools=tools,
                
            )
            stream.reasoning(
                "start",
                "Agent started"
            )
            responses_gen = agent(
                current_user_message=data.current_user_message,
                question_id=data.question_id,
            )
            buffer = ""
            CHUNK_SIZE = 200

            for token in responses_gen.response:
                buffer += token
                if len(buffer) >= CHUNK_SIZE:
                    stream.chunk(buffer)
                    buffer = ""
            if buffer:
                stream.chunk(buffer)

            stream.end()
            redis_client.expire(channel, 300)

        except Exception as e:
            stream.error(str(e))
            stream.end()

    bg.add_task(generate)

    return {
        "status": "started",
        "channel": channel
    }