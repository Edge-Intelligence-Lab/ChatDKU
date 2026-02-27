#!/usr/bin/env python

from redisvl.schema import IndexSchema

custom_schema = IndexSchema.from_dict(
    {
        "index": {
            "name": "idx:test",
            "prefix": "test_doc",
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
