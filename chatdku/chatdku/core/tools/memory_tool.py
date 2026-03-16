from mem0 import Memory

from chatdku.config import config


class MemoryTools:
    """Tools for interacting with the Mem0 memory system."""

    def __init__(self, user_id, session_id=""):
        self.user_id = user_id
        self.session_id = session_id
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
        }

        self.memory = Memory.from_config(memory_config)

    def store_memory(
        self,
        content: str | list[dict[str, str]],
    ) -> str:
        """Store information in memory.

        Args:
            content: The fact to be stored in memory.
            You should store information related to the user. For example it could be:
                - name of the user
                - user's major
                - user's graduation year
                - etc
            You should store the information you have asked from the user also.

        Returns:
            str: The result of the operation.
        """
        try:
            print(f"[DEBUG] Attempting to store memory for user_id={self.user_id}, session_id={self.session_id}")
            print(f"[DEBUG] Content: {content}")
            self.memory.add(content, user_id=self.user_id, run_id=self.session_id)
            return f"Stored memory: {content}"
        except Exception as e:
            return f"Error storing memory: {str(e)}"

    def search_memories(
        self,
        query: str,
        limit: int = 5,
    ) -> str:
        """Search for long-term memories

        This tool can also retrieve informations you have saved
        in your previous conversations with the user.

        Args:
            query: The query to search for.
            limit: The number of results to return.

        Returns:
            str: The result of the operation.
        """
        try:
            results = self.memory.search(
                query,
                user_id=self.user_id,
                limit=limit,
            )
            if not results:
                return "No relevant memories found."

            memory_text = "Relevant memories found:\n"
            for i, result in enumerate(results["results"]):
                memory_text += f"{i}. {result['memory']}\n"
            return memory_text
        except Exception as e:
            return f"Error searching memories: {str(e)}"

    def get_all_memories(
        self,
    ) -> str:
        """Get all memories for the user."""
        try:
            results = self.memory.get_all(user_id=self.user_id)
            if not results:
                return "No memories found for this user."

            memory_text = "All memories for user:\n"
            for i, result in enumerate(results["results"]):
                memory_text += f"{i}. {result['memory']}\n"
            return memory_text
        except Exception as e:
            return f"Error retrieving memories: {str(e)}"

    def update_memory(self, memory_id: str, new_content: str) -> str:
        """Update an existing memory."""
        try:
            self.memory.update(memory_id, new_content)
            return f"Updated memory with new content: {new_content}"
        except Exception as e:
            return f"Error updating memory: {str(e)}"

    def delete_memory(self, memory_id: str) -> str:
        """Delete a specific memory."""
        try:
            self.memory.delete(memory_id)
            return "Memory deleted successfully."
        except Exception as e:
            return f"Error deleting memory: {str(e)}"
   