from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from chatdku.core.dspy_classes.memory import PermanentMemory
from chatdku.core.tools.memory_tool import MemoryTools

app = FastAPI()


class MemoryRequestBase(BaseModel):
    user_id: str = Field(..., description="User identifier for memory scoping")
    session_id: str | None = Field(None, description="Optional session/run identifier")

class MemoryAgentRequest(MemoryRequestBase):
    session_conversation: list[dict[str, str]] | None = Field(
        None,
        description="Past conversation history for permanent memory planning",
    )
    most_recent_conversation: list[dict[str, str]] = Field(
        ...,
        description="Most recent conversation messages for permanent memory planning",
    )


def get_memory_tools(user_id: str, session_id: str | None = None) -> MemoryTools:
    return MemoryTools(user_id=user_id, session_id=session_id or "")



@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/memory")
async def memory_agent(request: MemoryAgentRequest):
    if request.most_recent_conversation is None:
        raise HTTPException(
            status_code=422,
            detail="most_recent_conversation is required",
        )
    if request.session_conversation is None:
        request.session_conversation = []
    permanent_memory = PermanentMemory(request.user_id)
    permanent_memory(
        session_conversation=request.session_conversation,
        most_recent_conversation=request.most_recent_conversation,
    )
    request.session_conversation.extend(request.most_recent_conversation)
    return {"conversations": request.session_conversation}
