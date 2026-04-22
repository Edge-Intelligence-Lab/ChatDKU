import asyncio
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from redis import Redis
from pydantic import BaseModel, Field
import json

from chatdku.core.dspy_classes.memory import PermanentMemory
from chatdku.core.tools.memory_tool import MemoryTools
from chatdku.config import config

app = FastAPI()
redis = Redis(host=config.redis_host, port=config.redis_port, password=config.redis_password)


class MemoryRequestBase(BaseModel):
    user_id: str = Field(..., description="User identifier for memory scoping")
    session_id: str | None = Field(None, description="Optional session/run identifier")

class MemoryAgentRequest(MemoryRequestBase):
    session_conversation: list[dict[str, str]] = Field(
        ...,
        description="Past conversation history for permanent memory planning",
    )
    most_recent_conversation: list[dict[str, str]] = Field(
        ...,
        description="Most recent conversation messages for permanent memory planning",
    )
    chat_id: str = Field(..., description="Chat identifier to know which conversation the memory belongs to")


def get_memory_tools(user_id: str, session_id: str | None = None) -> MemoryTools:
    return MemoryTools(user_id=user_id, session_id=session_id or "")



@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/memory")
def memory_agent(request: MemoryAgentRequest):
    if request.session_conversation is None:
        request.session_conversation = []

    channel = f"chat:{request.chat_id}"

    def publish(event_type : str, data : dict):
       redis.publish(channel, json.dumps({"event": event_type, "data": data}))
        
    publish("memory_agent_started", {"message": "Memory Agent started"})
    
    permanent_memory = PermanentMemory(user_id=request.user_id)
    
    publish("memory_agent_processing", {"message": "Processing memory agent request"})
    
    result = permanent_memory( 
        session_conversation=request.session_conversation,
        most_recent_conversation=request.most_recent_conversation,
    )
    
    publish("memory_agent_completed", {"message": "Memory Agent completed", "result": result}) # end token?
    
    return {"status": "success", "result": result}
    
    
    
