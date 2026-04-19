import asyncio
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from chatdku.core.dspy_classes.memory import PermanentMemory
from chatdku.core.tools.memory_tool import MemoryTools

app = FastAPI()


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
async def memory_agent(request: MemoryAgentRequest):
    if request.session_conversation is None:
        request.session_conversation = []

    async def event_generator():
        yield f"data: {json.dumps({'event': 'started'})}\n\n"

        permanent_memory = PermanentMemory(request.user_id)

        yield f"data: {json.dumps({'event': 'processing'})}\n\n"

        result = await asyncio.to_thread(
            permanent_memory,
            session_conversation=request.session_conversation,
            most_recent_conversation=request.most_recent_conversation,
        )

        request.session_conversation.extend(request.most_recent_conversation)

        yield f"data: {json.dumps({'event': 'done', 'result': result, 'conversations': request.session_conversation})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")