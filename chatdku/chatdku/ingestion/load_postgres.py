#!/usr/bin/env python3
"""load_postgres.py

Ingests LlamaIndex TextNodes into PostgreSQL + pgvector.

This loader stores content chunks in `{table_name}` and writes permissions into
`document_access`.

Important: the loader **must not** infer permissions. Permissions are defined
upstream in the parser stage (see `update_data.py`) by injecting these fields
into each node's metadata:

    access_type  : 'public' | 'student' | 'office' | 'private'   (required)
    role         : optional (defaults to 'student' for student access)
    organization : optional (required when access_type == 'office')
    user_id      : only meaningful when access_type == 'private'
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

"""NOTE

This file must remain a *dumb loader*:
    - parser stage writes permission metadata into each node
    - loader stores it (no inference, no validation, no defaulting)
    - retriever enforces it at query time
"""


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
            len(texts),
            e,
            half,
        )
        left = _embed_with_retry(embed_model, texts[:half], min_batch)
        right = _embed_with_retry(embed_model, texts[half:], min_batch)
        return left + right


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

-- Main table (partitioned)
CREATE TABLE IF NOT EXISTS {table_name} (
    id            TEXT,
    doc_id        TEXT,
    source_type   TEXT NOT NULL,
    text          TEXT NOT NULL,
    embedding     vector(1024),
    file_name     TEXT,
    user_id       TEXT,
    groups        TEXT,
    metadata      JSONB,
    text_search   tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED,
    PRIMARY KEY (id, source_type)
) PARTITION BY LIST (source_type);

-- doc partition
CREATE TABLE IF NOT EXISTS {table_name}_docs
PARTITION OF {table_name}
FOR VALUES IN ('doc');

-- event partition
CREATE TABLE IF NOT EXISTS {table_name}_events
PARTITION OF {table_name}
FOR VALUES IN ('event');

-- Permission table (used by PostgresRetriever)
CREATE TABLE IF NOT EXISTS document_access (
    doc_id         TEXT NOT NULL,
    source_type    TEXT,
    access_type    TEXT NOT NULL,  -- public | student | office | private
    role           TEXT,           -- student | faculty | ...
    organization   TEXT,           -- advising / registrar
    user_id        TEXT,           -- only for private
    PRIMARY KEY (doc_id, source_type, access_type, role, user_id)
);

-- Indexes (must be on parent so partitions get them on PG 11+)
CREATE INDEX IF NOT EXISTS {table_name}_text_search_idx
    ON {table_name} USING GIN (text_search);

CREATE INDEX IF NOT EXISTS {table_name}_doc_id_idx
    ON {table_name} (doc_id);

CREATE INDEX IF NOT EXISTS {table_name}_source_type_idx
    ON {table_name} (source_type);

-- ACL lookup index (doc_id is the join key in retriever)
CREATE INDEX IF NOT EXISTS document_access_doc_id_idx
    ON document_access (doc_id);
CREATE UNIQUE INDEX document_access_unique_idx
    ON document_access (
        doc_id, source_type, access_type, role, organization, user_id
    );
CREATE INDEX IF NOT EXISTS {table_name}_doc_id_source_type_idx
    ON {table_name} (doc_id, source_type);

-- Filter index (matches retriever's access predicate)
CREATE INDEX IF NOT EXISTS document_access_filter_idx
    ON document_access (source_type, access_type, role, organization, user_id);
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
    return psycopg2.connect(config.pg_ingest_uri)


def _prepare_batch(valid_pairs, embed_model):
    valid_nodes, texts = zip(*valid_pairs)
    embeddings = _embed_with_retry(embed_model, list(texts))

    rows = []
    acl_rows: set[tuple[str, str, str, str | None, str | None, str | None]] = set()
    for node, embedding, clean_text in zip(valid_nodes, embeddings, texts):
        promoted, rest = _split_metadata(node.metadata)
        if not node.ref_doc_id:
            raise ValueError(f"Node missing ref_doc_id: {node.node_id}")
        doc_id = _strip_nul(node.ref_doc_id or "")
        file_name = _strip_nul(promoted.get("file_name") or "")
        owner_user_id = _strip_nul(promoted.get("user_id") or "")
        groups_val = _strip_nul(promoted.get("groups") or "")

        st = "event" if node.metadata.get("is_event") else "doc"

        if doc_id:
            md = node.metadata or {}
            access_type = md.get("access_type")
            role = md.get("role")
            organization = md.get("organization")
            access_user_id = md.get("user_id")

            if access_type is None:
                raise ValueError(f"Missing access_type in node {node.node_id}")

            acl_rows.add(
                (
                    _strip_nul(str(doc_id)),
                    st,
                    access_type,
                    _strip_nul(str(role)) if role is not None else None,
                    _strip_nul(str(organization)) if organization is not None else None,
                    (
                        _strip_nul(str(access_user_id))
                        if access_user_id is not None
                        else None
                    ),
                )
            )

        rows.append(
            (
                _strip_nul(node.node_id),
                doc_id,
                st,
                clean_text,
                embedding,
                file_name,
                owner_user_id,
                groups_val,
                Json(
                    {
                        k: _strip_nul(v) if isinstance(v, str) else v
                        for k, v in rest.items()
                    }
                ),
            )
        )
    return rows, acl_rows


def _insert_batch(
    conn,
    cur,
    batch_nodes: list[TextNode],
    *,
    target_table_name: str,
    embed_model,
    batch_size: int = 25,
) -> None:

    if not batch_nodes:
        logger.info("No nodes to insert for table %s", target_table_name)
        return

    # ---- Embed + insert in batches -----------------------------------
    total = len(batch_nodes)
    for batch_start in range(0, total, batch_size):
        batch = batch_nodes[batch_start : batch_start + batch_size]

        valid_pairs = [(n, _strip_nul(n.text)) for n in batch if _is_valid_text(n.text)]
        skipped = len(batch) - len(valid_pairs)
        if skipped:
            logger.warning(
                "Skipping %d node(s) with empty/invalid text in this batch.", skipped
            )
        if not valid_pairs:
            continue

        rows, acl_rows = _prepare_batch(valid_pairs, embed_model=embed_model)

        execute_values(
            cur,
            f"""
            INSERT INTO {target_table_name}
                (id, doc_id, source_type, text, embedding, file_name, user_id, groups, metadata)
            VALUES %s
            ON CONFLICT (id, source_type) DO UPDATE SET
                doc_id    = EXCLUDED.doc_id,
                text      = EXCLUDED.text,
                embedding = EXCLUDED.embedding,
                file_name = EXCLUDED.file_name,
                user_id   = EXCLUDED.user_id,
                groups    = EXCLUDED.groups,
                metadata  = EXCLUDED.metadata
            """,
            rows,
            template="(%s, %s, %s, %s, %s::vector, %s, %s, %s, %s)",
        )

        if acl_rows:
            acl_rows_list = list(acl_rows)
            execute_values(
                cur,
                """
                INSERT INTO document_access
                    (doc_id, source_type, access_type, role, organization, user_id)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                acl_rows_list,
                template="(%s, %s, %s, %s, %s, %s)",
            )

        conn.commit()
        logger.info(
            "Inserted batch %d–%d / %d into %s",
            batch_start + 1,
            min(batch_start + batch_size, total),
            total,
            target_table_name,
        )


def load_postgres(
    nodes: Optional[list[TextNode]] = None,
    nodes_path: Optional[str] = None,
    table_name: Optional[str] = None,
    reset: bool = False,
    batch_size: int = 25,  # matches Chroma's buffer_size default; auto-halves on 413
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

    for node in nodes:
        # Normalise file_name (strip extension) to match legacy behaviour
        if "file_name" in node.metadata:
            node.metadata["file_name"] = _clean_file_name(node.metadata["file_name"])

    # table_name/event_table_name kept for CLI compatibility; loader inserts into chat_dku only.
    if table_name is None:
        table_name = getattr(config, "postgres_table", "chat_dku")

    logger.info(
        f"Target partitioned table: {table_name}  |  nodes: %d  |  reset: %s",
        len(nodes),
        reset,
    )

    # ---- 3. Database setup --------------------------------------------------
    conn = _get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    if reset:
        cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
        cur.execute("DROP TABLE IF EXISTS document_access CASCADE;")

    cur.execute(DDL.format(table_name=table_name))

    conn.commit()

    # ---- 4. Embed + insert in batches ---------------------------------------
    _insert_batch(
        conn,
        cur,
        nodes,
        target_table_name=table_name,
        batch_size=batch_size,
        embed_model=embed_model,
    )
    logger.info("PostgreSQL load done!")

    cur.close()
    conn.close()


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
        default="chat_dku",
        help="Target PostgreSQL table (default: 'chat_dku')",
    )
    parser.add_argument(
        "--reset",
        type=_str2bool,
        default=False,
        help="Drop and recreate the table before ingestion (default: False)",
    )
    args = parser.parse_args()
    main(args.nodes_path, args.table_name, args.reset)
