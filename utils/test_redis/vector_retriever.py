from redis import Redis
from redisvl.schema import IndexSchema
from llama_index.core import Settings
from llama_index.vector_stores.redis import RedisVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.embeddings.text_embeddings_inference import TextEmbeddingsInference


Settings.embed_model = TextEmbeddingsInference(
    model_name="BAAI/bge-m3",
    base_url="http://localhost:18080/BAAI/bge-m3",
)

redis_client = Redis.from_url("redis://localhost:6379")

vector_store = RedisVectorStore(
    redis_client=redis_client, schema=IndexSchema.from_yaml("custom_schema.yaml")
)
index = VectorStoreIndex.from_vector_store(vector_store)


def retrieve(query_str: str, groups: list[str]):
    filters = [MetadataFilter(key="groups", value=g, operator="in") for g in groups]
    retriever = index.as_retriever(
        similarity_top_k=5, filters=MetadataFilters(filters=filters, condition="or")
    )
    nodes = retriever.retrieve("quick")
    for node in nodes:
        print(node)


retrieve("quick", ["supervisor"])
print("---")
retrieve("quick", ["supervisor", "public"])
