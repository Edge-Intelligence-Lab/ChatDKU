from mem0 import Memory
from chatdku.core.tools.memory_tool import MemoryTools

import pytest

user_id = "test_user"

mt = MemoryTools(user_id=user_id)

def cleanup():
    # cleanup memories created during testing
    for mem in mt.memory.get_all(user_id=user_id).get("results", []):
        # print(f"Deleting memory: {mem['memory']} with ID: {mem['id']}")
        mt.delete_memory(mem["id"])
def test_memory_storage():
    # Test storing a memory
    memory_id = mt.store_memory("User is a computer science major.", metadata={"category": "academic", "entities": "major", "tags": "user_info", "time_relevance": "long-term"})
    assert memory_id is not None
def test_memory_retrieval():
    # Test retrieving memories
    cleanup()
    mem1_id = mt.store_memory("User is a computer science major.", metadata={"category": "academic", "entities": "major", "tags": "user_info", "time_relevance": "long-term"})
    mem2_id = mt.store_memory("User has a meeting with advisor tomorrow.", metadata={"category": "schedule", "entities": "meeting, advisor", "tags": "upcoming_event", "time_relevance": "short-term"})
    
    results = mt.search_memories("What is the user's major?")
    results = mt.last_memory_search
    for mem in results:
        print(mem["memory"], mem["metadata"])
    assert any("Major" in mem["memory"] for mem in results)
    # results = mt.search_memories("Does the user have any meetings?")
    # results = mt.last_memory_search
    # assert any("meeting" in mem["memory"] for mem in results)