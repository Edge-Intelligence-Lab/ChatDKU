#!/usr/bin/env python3
"""
load_postgres.py

Replaces load_redis.py and load_chroma.py.
Ingests LlamaIndex TextNodes into a unified PostgreSQL + pgvector table.

Schema per node:
  id            TEXT PRIMARY KEY
  doc_id        TEXT
  text          TEXT
  embedding     vector(1024)
  file_name     TEXT          -- structured for fast filtering
  user_id       TEXT          -- structured for fast filtering
  groups        TEXT          -- structured for fast filtering
  metadata      JSONB         -- remaining arbitrary metadata
  text_search   tsvector      -- sparse / BM25 search support

Index strategy (千级 chunk 规模):
  - No IVFFLAT / HNSW — plain sequential scan is more accurate at this scale.
  - GIN index on text_search for keyword retrieval.
  - B-tree indexes on file_name / user_id / groups for metadata filtering.
"""

import os
import json
import argparse
import logging
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values, Json
from llama_index.core.schema import TextNode
from llama_index.core import Settings

from chatdku.setup import setup
from chatdku.config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROMOTED_FIELDS = ("file_name", "user_id", "groups")  # fields pulled out of JSONB


def _clean_file_name(file_name: str) -> str:
    """Strip extension from file_name (preserves legacy behaviour from load_redis)."""
    return os.path.splitext(file_name)[0]


def _split_metadata(metadata: dict) -> tuple[dict, dict]:
    """
    Separate promoted scalar fields from the rest of the metadata.

    Returns
    -------
    promoted : dict  – keys are PROMOTED_FIELDS (value may be None)
    rest     : dict  – remaining metadata stored as JSONB
    """
    promoted = {f: metadata.get(f) for f in PROMOTED_FIELDS}
    rest = {k: v for k, v in metadata.items() if k not in PROMOTED_FIELDS}
    return promoted, rest


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS {table} (
    id            TEXT PRIMARY KEY,
    doc_id        TEXT,
    text          TEXT NOT NULL,
    embedding     vector(1024),
    file_name     TEXT,
    user_id       TEXT,
    groups        TEXT,
    metadata      JSONB,
    text_search   tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED
);

-- Sparse / keyword search
CREATE INDEX IF NOT EXISTS {table}_text_search_idx
    ON {table} USING GIN (text_search);

-- Metadata filters
CREATE INDEX IF NOT EXISTS {table}_file_name_idx
    ON {table} (file_name);

CREATE INDEX IF NOT EXISTS {table}_user_id_idx
    ON {table} (user_id);

CREATE INDEX IF NOT EXISTS {table}_groups_idx
    ON {table} (groups);
"""

# NOTE: No ANN vector index is created intentionally.
# Sequential scan gives 100 % recall and is fast enough for thousands of rows.
# Add an HNSW index here once the table grows beyond ~50 k rows:
#
#   CREATE INDEX {table}_embedding_hnsw_idx
#       ON {table} USING hnsw (embedding vector_cosine_ops);


# ---------------------------------------------------------------------------
# Core ingestion
# ---------------------------------------------------------------------------

def _get_connection() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=config.postgres_host,
        port=getattr(config, "postgres_port", 5432),
        dbname=config.postgres_db,
        user=config.postgres_user,
        password=config.postgres_password,
    )


def load_postgres(
    nodes: Optional[list[TextNode]] = None,
    nodes_path: Optional[str] = None,
    table_name: Optional[str] = None,
    reset: bool = False,
    batch_size: int = 64,
) -> None:
    """
    Ingest TextNodes into PostgreSQL + pgvector.

    Parameters
    ----------
    nodes       : pre-built list of TextNode objects (optional).
    nodes_path  : path to a nodes.json file (used when *nodes* is None).
    table_name  : target table; falls back to config.postgres_table.
    reset       : if True, DROP and recreate the table before ingestion.
    batch_size  : rows per INSERT batch.
    """
    # ---- 1. Embeddings setup ------------------------------------------------
    setup(use_llm=False)
    embed_model = Settings.embed_model

    # ---- 2. Load nodes ------------------------------------------------------
    if nodes is None:
        if nodes_path is None:
            nodes_path = config.nodes_path
        logger.info("Loading nodes from %s", nodes_path)
        with open(nodes_path, "r") as fh:
            datas = json.load(fh)
        nodes = [TextNode.from_dict(d) for d in datas]

    # Normalise file_name (strip extension) to match legacy behaviour
    for node in nodes:
        if "file_name" in node.metadata:
            node.metadata["file_name"] = _clean_file_name(node.metadata["file_name"])

    if table_name is None:
        table_name = getattr(config, "postgres_table", "chatdku")

    logger.info("Target table: %s  |  nodes: %d  |  reset: %s",
                table_name, len(nodes), reset)

    # ---- 3. Database setup --------------------------------------------------
    conn = _get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    if reset:
        logger.info("Dropping table %s", table_name)
        cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")

    cur.execute(DDL.format(table=table_name))
    conn.commit()

    # ---- 4. Embed + insert in batches ---------------------------------------
    total = len(nodes)
    for batch_start in range(0, total, batch_size):
        batch = nodes[batch_start: batch_start + batch_size]

        # Embed texts
        texts = [n.text for n in batch]
        embeddings = embed_model.get_text_embedding_batch(texts, show_progress=False)

        rows = []
        for node, embedding in zip(batch, embeddings):
            promoted, rest = _split_metadata(node.metadata)
            rows.append((
                node.node_id,                       # id
                node.ref_doc_id,                    # doc_id
                node.text,                          # text
                embedding,                          # embedding  (list[float])
                promoted.get("file_name"),          # file_name
                promoted.get("user_id"),            # user_id
                promoted.get("groups"),             # groups
                Json(rest),                         # metadata JSONB
            ))

        execute_values(
            cur,
            f"""
            INSERT INTO {table_name}
                (id, doc_id, text, embedding, file_name, user_id, groups, metadata)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                doc_id    = EXCLUDED.doc_id,
                text      = EXCLUDED.text,
                embedding = EXCLUDED.embedding,
                file_name = EXCLUDED.file_name,
                user_id   = EXCLUDED.user_id,
                groups    = EXCLUDED.groups,
                metadata  = EXCLUDED.metadata
            """,
            rows,
            template=(
                "(%s, %s, %s, %s::vector, %s, %s, %s, %s)"
            ),
        )
        conn.commit()
        logger.info("Inserted batch %d–%d / %d",
                    batch_start + 1, min(batch_start + batch_size, total), total)

    cur.close()
    conn.close()
    logger.info("PostgreSQL load done!")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _str2bool(val):
    if isinstance(val, bool):
        return val
    if val.lower() in ("t", "true", "1", "yes"):
        return True
    if val.lower() in ("f", "false", "0", "no"):
        return False
    raise ValueError(f"Cannot parse boolean from: {val!r}")


def main(nodes_path=None, table_name=None, reset=False):
    load_postgres(
        nodes_path=nodes_path,
        table_name=table_name,
        reset=reset,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Ingest nodes.json into PostgreSQL + pgvector."
    )
    parser.add_argument(
        "--nodes_path",
        type=str,
        default=config.nodes_path,
        help="Path to nodes.json (default: config.nodes_path)",
    )
    parser.add_argument(
        "--table_name",
        type=str,
        default="chat_dku_docs",
        help="Target PostgreSQL table (default: config.postgres_table or 'chatdku')",
    )
    parser.add_argument(
        "--reset",
        type=_str2bool,
        default=False,
        help="Drop and recreate the table before ingestion (default: False)",
    )
    args = parser.parse_args()
    main(args.nodes_path, args.table_name, args.reset)