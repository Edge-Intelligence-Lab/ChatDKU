from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from chatdku.core.tools.memory_tool import MemoryTools

app = FastAPI()


class MemoryRequestBase(BaseModel):
    user_id: str = Field(..., description="User identifier for memory scoping")
    session_id: str | None = Field(None, description="Optional session/run identifier")

class StoreMemoryRequest(MemoryRequestBase):
    content: str | list[dict[str, str]] = Field(
        ..., description="Memory content or list of role/content items"
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description="Optional metadata for the memory. Values should be primitive types.",
    )

class SearchMemoryRequest(MemoryRequestBase):
    query: str = Field(..., description="Search query")
    limit: int = Field(5, description="Maximum number of memories to return")
    filters: dict[str, Any] | None = Field(None, description="Optional metadata filters")


class UpdateMemoryRequest(MemoryRequestBase):
    idx: int = Field(..., description="Index from a previous search result")
    new_content: str = Field(..., description="New content for the selected memory")


class DeleteMemoryRequest(MemoryRequestBase):
    memory_id: str = Field(..., description="Memory ID to delete")


def get_memory_tools(user_id: str, session_id: str | None = None) -> MemoryTools:
    return MemoryTools(user_id=user_id, session_id=session_id or "")


@app.get("/")
async def root():
    return {"status": "ok"}


@app.post("/memory/search")
async def search_memories(request: SearchMemoryRequest):
    tools = get_memory_tools(request.user_id, request.session_id)
    result = tools.search_memories(request.query, limit=request.limit, filters=request.filters)
    return {"result": result}

@app.post("/memory/store")
async def store_memory(request: StoreMemoryRequest):
    tools = get_memory_tools(request.user_id, request.session_id)
    result = tools.store_memory(request.content, metadata=request.metadata)
    return {"result": result}


@app.post("/memory/update")
async def update_memory(request: UpdateMemoryRequest):
    tools = get_memory_tools(request.user_id, request.session_id)
    result = tools.update_memory(request.idx, request.new_content)
    return {"result": result}


@app.delete("/memory/{memory_id}")
async def delete_memory(
    memory_id: str,
    user_id: str = Query(..., description="User identifier for memory scoping"),
    session_id: str | None = Query(None, description="Optional session/run identifier"),
):
    tools = get_memory_tools(user_id, session_id)
    result = tools.delete_memory(memory_id)
    if result.startswith("Error"):
        raise HTTPException(status_code=400, detail=result)
    return {"result": result}


@app.post("/memory/cleanup") # I might not need this cuz I have it built into the store_memory function
async def cleanup_memory(
    user_id: str = Query(..., description="User identifier for memory scoping"),
    session_id: str | None = Query(None, description="Optional session/run identifier"),
    max_memories: int = Query(100, description="Maximum number of memories to retain"),
):
    tools = get_memory_tools(user_id, session_id)
    result = tools.cleanup_memory(max_memories=max_memories)
    return {"result": result}
