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


def _strip_nul(value: str) -> str:
    """Remove NUL (0x00) characters that PostgreSQL string literals cannot contain."""
    return value.replace("\x00", "")


def _is_valid_text(text) -> bool:
    """
    Mirror the guard used in load_chroma.py:
        if not node.text or not isinstance(node.text, str): continue

    Also rejects strings that become empty / whitespace-only after NUL removal,
    because the TEI embedding server returns HTTP 413 for such payloads even
    when the byte length is tiny (chars=2 still fails).
    """
    if not text or not isinstance(text, str):
        return False
    cleaned = text.replace("\x00", "").strip()
    return bool(cleaned)


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


def _embed_with_retry(embed_model, texts: list[str], min_batch: int = 1) -> list:
    """
    Call embed_model.get_text_embedding_batch, automatically halving the sub-batch
    on HTTP 413 / payload-too-large errors until min_batch is reached.

    Why this is needed
    ------------------
    The TEI server enforces a hard payload limit per request.  load_chroma.py
    avoided hitting it by using buffer_size=25; our batch_size was accidentally
    set to 64 which blew the limit.  Rather than hard-coding a magic number we
    retry adaptively: any failure halves the batch and retries each half
    independently, converging to single-item batches in the worst case.
    """
    if not texts:
        return []

    try:
        result = embed_model.get_text_embedding_batch(texts, show_progress=False)
        # LlamaIndex returns a dict (not a list) when the server signals an error
        if not isinstance(result, list):
            raise ValueError(f"Embedding server returned an error payload: {result}")
        return result
    except Exception as e:
        half = len(texts) // 2
        if half < min_batch:
            raise RuntimeError(
                f"Embedding failed on a single chunk (chars={len(texts[0])})."
                " The chunk itself may exceed the TEI server's payload limit."
            ) from e
        logger.warning(
            "Embedding batch of %d failed (%s) — retrying as two halves of %d.",
            len(texts), e, half,
        )
        left  = _embed_with_retry(embed_model, texts[:half],  min_batch)
        right = _embed_with_retry(embed_model, texts[half:], min_batch)
        return left + right


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
    batch_size: int = 25,   # matches Chroma's buffer_size default; auto-halves on 413
) -> None:
    """
    Ingest TextNodes into PostgreSQL + pgvector.

    Parameters
    ----------
    nodes       : pre-built list of TextNode objects (optional).
    nodes_path  : path to a nodes.json file (used when *nodes* is None).
    table_name  : target table; falls back to config.postgres_table.
    reset       : if True, DROP and recreate the table before ingestion.
    batch_size  : texts per embedding request.  Defaults to 25 (same as the
                  legacy Chroma loader) to stay within TEI's payload limit.
                  Automatically halved on HTTP 413 / server error responses.
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

        # Filter out invalid nodes (empty / non-string text) before embedding.
        # Chroma does the same: "if not node.text or not isinstance(node.text, str): continue"
        # The TEI server returns HTTP 413 even for a single chunk whose text is
        # blank or whitespace-only after NUL removal, so we must drop them here.
        valid_pairs = [
            (n, _strip_nul(n.text))
            for n in batch
            if _is_valid_text(n.text)
        ]
        skipped = len(batch) - len(valid_pairs)
        if skipped:
            logger.warning("Skipping %d node(s) with empty/invalid text in this batch.", skipped)
        if not valid_pairs:
            continue

        valid_nodes, texts = zip(*valid_pairs)   # unzip into two tuples

        # Embed — retries with smaller sub-batches on 413 / server errors
        embeddings = _embed_with_retry(embed_model, list(texts))

        rows = []
        for node, embedding, clean_text in zip(valid_nodes, embeddings, texts):
            promoted, rest = _split_metadata(node.metadata)
            # Sanitise every string field — NUL (0x00) anywhere causes psycopg2 to raise
            rows.append((
                _strip_nul(node.node_id),                        # id
                _strip_nul(node.ref_doc_id or ""),               # doc_id
                clean_text,                                      # text (already cleaned)
                embedding,                                       # embedding (list[float])
                _strip_nul(promoted.get("file_name") or ""),     # file_name
                _strip_nul(promoted.get("user_id") or ""),       # user_id
                _strip_nul(promoted.get("groups") or ""),        # groups
                Json({k: (_strip_nul(v) if isinstance(v, str) else v)
                      for k, v in rest.items()}),                # metadata JSONB
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
            template="(%s, %s, %s, %s::vector, %s, %s, %s, %s)",
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
        help="Target PostgreSQL table (default: 'chat_dku_docs')",
    )
    parser.add_argument(
        "--reset",
        type=_str2bool,
        default=False,
        help="Drop and recreate the table before ingestion (default: False)",
    )
    args = parser.parse_args()
    main(args.nodes_path, args.table_name, args.reset)