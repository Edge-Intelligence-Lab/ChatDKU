import time

from mem0 import Memory

from chatdku.config import config
from chatdku.core.dspy_classes.prompt_settings import custom_fact_extraction_prompt
import os

class MemoryTools:
    """Tools for interacting with the Mem0 memory system."""

    def __init__(self, user_id, session_id=""):
        self.user_id = user_id
        self.session_id = session_id
        self.last_memory_search = []
        self.last_searched_times = {}  # memory_id -> last_searched_timestamp
        self.op_count = 0
        # Setting up agent memory
        memory_config = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": config.memory_collection,
                    "host": "localhost",
                    "port": config.chroma_db_port,
                },
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": config.llm,
                    "temperature": 0.1,
                    "openai_base_url": config.llm_url,
                    "api_key": config.llm_api_key,
                },
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": config.embedding,
                    "embedding_dims": 1024,
                    "huggingface_base_url": config.tei_url + "/" + config.embedding,
                },
            },
            "custom_fact_extraction_prompt": custom_fact_extraction_prompt,
        }

        self.memory = Memory.from_config(config_dict=memory_config)

    def store_memory(
        self,
        content: str | list[dict[str, str]], metadata: dict | None = None,
    ) -> str:
        """Store information in memory along with metadata.

        Args:
            content: The fact to be stored in memory.
            metadata: optional dictionary of metadata to associate with the memory.
                      All metadata values must be a single primitive (str, int, float, bool), or None
                      If you store multiple items(e.g., multiple tags), encode them as a comma-separated string.

        You should store information related to the user. For example it could be:
            - name of the user
            - user's major
            - user's graduation year
            - etc
        You should store the information you have asked from the user also.

        Guidelines for time relevance:
            - "long-term": stable facts that are useful across conversations
                Examples: 
                - "User is a computer science major"
                - "User prefers evening classes"
            - "short-term": recent or context-specific information
                Examples:
                - "User is currently stressed about upcoming exams"
                - "User is going to be late on an assignment today"

        In addition to storing memory content, you should extract metadata from the content and store it as well.
        Metadata can include:
        - category (e.g., academic, personal, preference)
        - entities (e.g., course names, majors, locations)
        - tags (keywords)
        - time relevance (e.g., short-term, long-term)

        Do NOT store:
            - task-specific requests (e.g., "help me plan my schedule")
            - one-time clarifications (e.g., "I meant Bio110, not Bio101")
            - general questions or instructions
            - weak or irrelevant information

        
        Example Usage:
            store_memory(
                "User will attend a guest lecture today.",
                metadata={
                    "category": "academic",
                    "entities": "lecture",
                    "tags": "user_info",
                    "time_relevance": "short-term"
                }
            )
        Returns:
            str: The result of the operation.
        """
        try:
            self.memory.add(content, user_id=self.user_id, run_id=self.session_id, metadata=metadata)
            self.op_count += 1

            if self.op_count % 10 == 0:
                self.cleanup_memory()
            return f"Stored memory: {content}"
        except Exception as e:
            return f"Error storing memory: {str(e)}"

    def search_memories(
        self,
        query: str,
        limit: int = 5,
        filters: dict | None = None,
    ) -> str:
        """
        Searches the user's long term memories

        Args:
            query: The text string to search for in memory.
            limit: The maximum number of relevant memories to return, defaults to 5
            filters: Optional dictionary of metadata filters to apply to the search.
                     Example: 
                     {
                        "category": "academic",
                        "entities": "Bio110",
                        "time_relevance": "long-term"
                        "tags": "course_info"
                     }

        Returns a formatted string with indicies, ID's, and metadata.
        """
        try:
            results = self.memory.search(
                query,
                user_id=self.user_id,
                limit=limit,
                filters=filters
            )
            if not results or not results.get("results"):
                self.last_memory_search = []  # Clear last search results if no results found
                return "No Relevant memories found."

            self.last_memory_search = results["results"]  # Store the last search results
            memory_text = "Relevant memories found:\n"

            if not hasattr(self, "memory_access_log"):
                self.memory_access_log = {}

            for idx, mem in enumerate(results["results"]):
                memory_id = mem["id"]
                if memory_id not in self.memory_access_log:
                    self.memory_access_log[memory_id] = {
                        "count": 0,
                        "last_accessed": None
                    }
                self.memory_access_log[memory_id]["count"] += 1
                self.memory_access_log[memory_id]["last_accessed"] = time.time()

                access_info = self.memory_access_log[memory_id]

                memory_text += (
                    f"{idx}. Memory: {mem['memory']}\n"
                    f"   ID: {mem['id']}\n"
                    f"   Metadata: {mem.get('metadata')}\n"
                    f"   Access Count: {access_info['count']}\n"
                    f"   Last Accessed: {access_info['last_accessed']}\n"
                ) 
            return memory_text
        except Exception as e:
            return f"Error searching memories: {str(e)}"

    def get_all_memories(
        self,
    ) -> str:
        """Get all memories for the user."""
        try:
            results = self.memory.get_all(user_id=self.user_id)
            if not results or not results.get("results"):
                return "No memories found for this user."

            memory_text = "All memories for user:\n"
            for i, memory in enumerate(results["results"]):
                memory_text += (
                    f"{i}. Memory: {memory['memory']}\n"
                    f"   ID: {memory['id']}\n"
                    f"   Metadata: {memory.get('metadata')}\n"
                    f"   Created: {memory['created_at']}\n"
                    f"   Updated: {memory.get('updated_at')}\n"
                )

            return memory_text
        except Exception as e:
            return f"Error retrieving memories: {str(e)}"

    def update_memory(self, idx: int, new_content: str, ) -> str:
        """Update an existing memory."""
        try:
            if(idx>=len(self.last_memory_search)):
                return "Invalid memory index. Please search for memories again to get the correct index."
            
            memory_id = self.last_memory_search[idx]["id"]  # Get the memory ID using the index from the last search results
            self.memory.update(memory_id, new_content)
            
            return f"Updated memory {idx} with new content: {new_content}"
        except Exception as e:
            return f"Error updating memory: {str(e)}"

    def delete_memory(self, memory_id: str) -> str:
        """Delete a specific memory. Important: call search_memories first to get the memory_id, do NOT guess or generate memory IDs."""
        try:
            self.memory.delete(memory_id)
            return f"Memory with id:{memory_id} deleted successfully."
        except Exception as e:
            return f"Error deleting memory: {str(e)}"

    def cleanup_memory(self, max_memories: int = 100 ) -> str:
        """Cleanup unused memories for the user. """
        try:
            deleted_count = 0
            all_memories = self.memory.get_all(user_id=self.user_id)
            if not all_memories or not all_memories.get("results"):
                return "No memories to clean."


            sorted_mems = sorted(
                        all_memories["results"],
                        key=lambda m: self.memory_access_log.get(m["id"], {"last_accessed": 0})["last_accessed"] or 0
                    )  

            while sorted_mems:
                memory = sorted_mems[0]  # Get the least recently accessed memory
                metadata = memory.get("metadata", {}) or {}

                mem_id = memory["id"]
                to_delete=False

                if metadata.get("time_relevance") == "temporary":
                    to_delete=True
                elif len(sorted_mems) > max_memories:
                    to_delete = True

                if to_delete:
                    self.memory.delete(memory["id"])
                    deleted_count += 1
                    sorted_mems.pop(0) # remove from list
                    if(mem_id in self.memory_access_log):
                        del self.memory_access_log[mem_id] # remove from access log
                else:
                    break  # Stop deleting if we are under the max memory limit

            return f"Cleanup memories completed successfully. Deleted {deleted_count} memories."
        except Exception as e:
            return f"Error cleaning up memories: {str(e)}"




if __name__ == "__main__":
    # Example usage
    user_id = "user123"
    memory_tool = MemoryTools(user_id)
    print(memory_tool.store_memory("User's name is Alice."))
    print(memory_tool.search_memories("What is the user's name?"))
    print(memory_tool.get_all_memories())

    print(memory_tool.update_memory(0, "User's name is Bob."))
    print(memory_tool.get_all_memories())

    # print(memory_tool.delete_memory(0))
    os._exit(0)