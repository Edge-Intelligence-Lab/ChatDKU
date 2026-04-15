from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from chatdku.core.dspy_classes.memory import PermanentMemory
from chatdku.core.tools.memory_tool import MemoryAgent, MemoryTools

app = FastAPI()


class MemoryRequestBase(BaseModel):
    user_id: str = Field(..., description="User identifier for memory scoping")
    session_id: str | None = Field(None, description="Optional session/run identifier")

class MemoryAgentRequest(MemoryRequestBase):
    action: Literal["store", "search", "get_all", "update", "delete", "cleanup", "permanent"] = Field(
        ..., description="Memory action to perform"
    )
    content: str | list[dict[str, str]] | None = Field(
        None, description="Memory content or list of role/content items"
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description="Optional metadata for the memory. Values should be primitive types.",
    )
    query: str | None = Field(None, description="Search query")
    limit: int = Field(5, description="Maximum number of memories to return")
    filters: dict[str, Any] | None = Field(None, description="Optional metadata filters")
    idx: int | None = Field(None, description="Index from a previous search result")
    new_content: str | None = Field(None, description="New content for the selected memory")
    memory_id: str | None = Field(None, description="Memory ID to delete")
    max_memories: int = Field(100, description="Maximum number of memories to retain")
    session_conversation: list[dict[str, str]] | None = Field(
        None,
        description="Past conversation history for permanent memory planning",
    )
    most_recent_conversation: list[dict[str, str]] | None = Field(
        None,
        description="Most recent conversation messages for permanent memory planning",
    )



def get_memory_tools(user_id: str, session_id: str | None = None) -> MemoryTools:
    return MemoryTools(user_id=user_id, session_id=session_id or "")


def get_memory_agent(user_id: str, session_id: str | None = None) -> MemoryAgent:
    return MemoryAgent(user_id=user_id, session_id=session_id or "")


@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/memory")
async def memory_agent(request: MemoryAgentRequest):
    if request.action == "permanent":
        if request.session_conversation is None or request.most_recent_conversation is None:
            raise HTTPException(
                status_code=422,
                detail="session_conversation and most_recent_conversation are required for action 'permanent'",
            )
        permanent_memory = PermanentMemory(request.user_id)
        permanent_memory.forward(
            session_conversation=request.session_conversation,
            most_recent_conversation=request.most_recent_conversation,
        )
        return {"result": "PermanentMemory.forward executed"}

    agent = get_memory_agent(request.user_id, request.session_id)
    payload = {
        "content": request.content,
        "metadata": request.metadata,
        "query": request.query,
        "limit": request.limit,
        "filters": request.filters,
        "idx": request.idx,
        "new_content": request.new_content,
        "memory_id": request.memory_id,
        "max_memories": request.max_memories,
    }
    result = agent.handle(request.action, **payload)
    if isinstance(result, str) and result.startswith("Error"):
        raise HTTPException(status_code=400, detail=result)
    return {"result": result}
