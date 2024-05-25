from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# TODO: Use a better embedding model
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en-v1.5", trust_remote_code=True
)
# TODO: Add LLM
Settings.llm = None
