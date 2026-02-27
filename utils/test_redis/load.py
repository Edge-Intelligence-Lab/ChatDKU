from llama_index.core.schema import TextNode
from redis import Redis
from redisvl.schema import IndexSchema
from llama_index.vector_stores.redis import RedisVectorStore

from llama_index.embeddings.text_embeddings_inference import TextEmbeddingsInference
from llama_index.core.ingestion import IngestionPipeline

documents = [
    TextNode(text="alpha alpha alpha alpha"),
    TextNode(text="beta beta beta"),
    TextNode(text="alpha beta gamma gamma"),
]

redis_client = Redis.from_url("redis://localhost:6379")

custom_schema = IndexSchema.from_dict(
    {
        "index": {
            "name": "idx:test_1",
            "prefix": "test_doc_1",
            "key_separator": ":",
        },
        "fields": [
            # Required fields for llamaindex
            {"type": "tag", "name": "id"},
            {"type": "tag", "name": "doc_id"},
            {"type": "text", "name": "text"},
            # Custom metadata fields
            {"type": "tag", "name": "groups"},
            # Custom vector embeddings field definition
            {
                "type": "vector",
                "name": "vector",
                "attrs": {
                    # NOTE: This should match the size of the vector embeddings
                    "dims": 1024,
                    "algorithm": "hnsw",
                    "distance_metric": "cosine",
                },
            },
        ],
    }
)
custom_schema.to_yaml("custom_schema.yaml")

vector_store = RedisVectorStore(
    redis_client=redis_client, schema=custom_schema, overwrite=True
)

embed_model = TextEmbeddingsInference(
    model_name="BAAI/bge-m3",
    base_url="http://localhost:18080/BAAI/bge-m3",
)

pipeline = IngestionPipeline(
    transformations=[embed_model],
    vector_store=vector_store,
)
nodes = pipeline.run(documents=documents, num_workers=1, show_progress=True)
