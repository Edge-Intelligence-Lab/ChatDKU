#!/usr/bin/env python3
"""
postgres_retriever.py

Drop-in replacement for VectorRetriever + KeywordRetriever.
Implements BaseDocRetriever.query() using PostgreSQL + pgvector.

Hybrid search strategy:
  - Dense  : cosine similarity via pgvector  (<=> operator)
  - Sparse : tsvector / tsquery full-text ranking (ts_rank)
  - Results are merged by RRF (Reciprocal Rank Fusion) inside SQL,
    so no application-level merging is needed.

The public interface (constructor signature + return type of query())
is identical to VectorRetriever / KeywordRetriever, so DocRetrieverOuter
requires zero changes.
"""

from __future__ import annotations

import psycopg2
from llama_index.core import Settings

from chatdku.config import config
from chatdku.core.tools.retriever.base_retriever import BaseDocRetriever, NodeWithScore
from chatdku.core.tools.utils import get_url

from chatdku.setup import setup

class PostgresRetriever(BaseDocRetriever):
    """
    Hybrid (dense + sparse) retriever backed by PostgreSQL + pgvector.

    Parameters mirror VectorRetriever / KeywordRetriever exactly so that
    DocRetrieverOuter can swap them in without any interface changes.
    """

    def __init__(
        self,
        internal_memory: dict,
        retriever_top_k: int = 25,
        user_id: str = "Chat_DKU",
        search_mode: int = 0,
        files: list | None = None,
        table_name: str | None = None,
        rrf_k: int = 60,
    ):
        super().__init__(internal_memory, retriever_top_k, user_id, search_mode, files)
        self.table_name = table_name or getattr(config, "postgres_table", "chatdku")
        self.rrf_k = rrf_k  # RRF constant; 60 is the standard default

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_connection(self) -> psycopg2.extensions.connection:
        return psycopg2.connect(
            host=config.postgres_host,
            port=getattr(config, "postgres_port", 5432),
            dbname=config.postgres_db,
            user=config.postgres_user,
            password=config.postgres_password,
        )

    def _embed(self, query: str) -> list[float]:
        return Settings.embed_model.get_query_embedding(query)

    def _build_where_clause(self) -> tuple[str, list]:
        """
        Translate search_mode / user_id / files / exclude into a SQL WHERE
        fragment and its positional parameters.

        Mirrors __get_chroma_filter() logic from VectorRetriever.
        """
        params: list = []
        conditions: list[str] = []

        if self.search_mode == 0:
            conditions.append("user_id = %s")
            params.append(self.user_id)

        elif self.search_mode == 1:
            conditions.append("user_id = %s")
            params.append(self.user_id)
            conditions.append("file_name = ANY(%s)")
            params.append(self.files or [])

        elif self.search_mode == 2:
            conditions.append(
                "(user_id = %s OR (user_id = %s AND file_name = ANY(%s)))"
            )
            params.extend([config.default_user_id, self.user_id, self.files or []])

        if self.exclude:
            conditions.append("id <> ALL(%s)")
            params.append(list(self.exclude))

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return where, params

    # ------------------------------------------------------------------
    # Core query — matches the return type of VectorRetriever.query()
    # ------------------------------------------------------------------

    def query(self, query: str) -> list[NodeWithScore]:
        """
        Hybrid search: dense (pgvector cosine) + sparse (tsvector).
        Results are fused with Reciprocal Rank Fusion and the top
        `retriever_top_k` nodes are returned as NodeWithScore objects.
        """
        embedding = self._embed(query)
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        where, base_params = self._build_where_clause()

        if where:
            sparse_where = where + " AND text_search @@ plainto_tsquery('english', %s)"
        else:
            sparse_where = "WHERE text_search @@ plainto_tsquery('english', %s)"

        # RRF over dense and sparse rankings, both restricted by the same WHERE.
        # base_params appears twice (once for dense CTE, once for sparse CTE).
        sql = f"""
        WITH
        dense AS (
            SELECT id, text, metadata, file_name,
                   ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
            FROM {self.table_name}
            {where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        ),
        sparse AS (
            SELECT id, text, metadata, file_name,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank(text_search, plainto_tsquery('english', %s)) DESC
                   ) AS rank
            FROM {self.table_name}
            {sparse_where}
            ORDER BY rank
            LIMIT %s
        ),
        fused AS (
            SELECT
                COALESCE(d.id,       s.id)        AS id,
                COALESCE(d.text,     s.text)       AS text,
                COALESCE(d.metadata, s.metadata)   AS metadata,
                COALESCE(d.file_name,s.file_name)  AS file_name,
                (
                    COALESCE(1.0 / (%s + d.rank), 0) +
                    COALESCE(1.0 / (%s + s.rank), 0)
                ) AS rrf_score
            FROM dense d
            FULL OUTER JOIN sparse s USING (id)
        )
        SELECT id, text, metadata, file_name, rrf_score
        FROM fused
        ORDER BY rrf_score DESC
        LIMIT %s;
        """

        # Positional params in placeholder order:
        #   dense CTE  : embedding_str, *where_params, embedding_str, top_k
        #   sparse CTE : query,         *where_params, query,         top_k
        #   RRF        : rrf_k, rrf_k
        #   final LIMIT: top_k
        all_params = (
            [embedding_str] + base_params + [embedding_str, self.retriever_top_k]
            + [query]        + base_params + [query,         self.retriever_top_k]
            + [self.rrf_k, self.rrf_k]
            + [self.retriever_top_k]
        )

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, all_params)
                rows = cur.fetchall()
        finally:
            conn.close()

        return [
            NodeWithScore(
                node_id=row[0],
                text=row[1],
                metadata={
                    "file_name": row[3],
                    "url": get_url(row[2] or {}),
                    "page_number": (row[2] or {}).get("page_number"),
                },
                score=float(row[4]),
            )
            for row in rows
        ]

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Test PostgresRetriever")
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Query text for retrieval test",
    )
    parser.add_argument(
        "--top_k",
        type=int,
        default=5,
        help="Number of results to return",
    )
    parser.add_argument(
        "--user_id",
        type=str,
        default="Chat_DKU",
        help="User ID filter",
    )
    parser.add_argument(
        "--search_mode",
        type=int,
        default=0,
        help="Search mode (0=user, 1=user+files, 2=global+files)",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Optional file_name filter list",
    )

    args = parser.parse_args()

    setup(use_llm=False)
    
    retriever = PostgresRetriever(
        internal_memory={},
        retriever_top_k=args.top_k,
        user_id=args.user_id,
        search_mode=args.search_mode,
        files=args.files,
    )

    results = retriever.query(args.query)

    print("\n=== Retrieval Results ===\n")

    for i, r in enumerate(results, 1):
        print(f"Rank {i}")
        print("Score:", r.score)
        print("Node ID:", r.node_id)
        print("Metadata:", json.dumps(r.metadata, indent=2))
        print("Text preview:", r.text[:300].replace("\n", " "))
        print("-" * 60)