#!/usr/bin/env python3
"""
postgres_retriever.py

Drop-in replacement for VectorRetriever + KeywordRetriever.
Implements BaseDocRetriever.query() using PostgreSQL + pgvector.

Hybrid search strategy:
  - Dense  : cosine similarity via pgvector HNSW index (<=> operator)
  - Sparse : tsvector GIN index full-text ranking (ts_rank)
  - Results merged by RRF (Reciprocal Rank Fusion) via UNION ALL + GROUP BY

Performance fixes applied vs original:
  1. HNSW index + SET LOCAL hnsw.ef_search  → O(log N) ANN
  2. Single-sort dense/sparse CTEs via subquery  → eliminates duplicate window sort
  3. GIN index on text_search  → sparse search hits index, not seq scan
  4. Module-level SimpleConnectionPool  → no per-query TCP handshake
  5. Embedding passed as native Python list  → no manual string serialisation
  6. RRF via UNION ALL + GROUP BY  → replaces expensive FULL OUTER JOIN
"""

from __future__ import annotations
from time import perf_counter

from psycopg2 import extensions as pg_ext
from psycopg2.pool import SimpleConnectionPool
from llama_index.core import Settings

from chatdku.config import config
from chatdku.core.tools.retriever.base_retriever import BaseDocRetriever, NodeWithScore
from chatdku.core.tools.utils import get_url

from contextlib import suppress
from dataclasses import dataclass
from functools import lru_cache
from threading import BoundedSemaphore
from typing import Any
import inspect


# ---------------------------------------------------------------------------
# Fix #4 — module-level connection pool (one pool per process, lazy init)
# ---------------------------------------------------------------------------
_pool: SimpleConnectionPool | None = None


# +++ added: global concurrency limiter (prevents DB overload under concurrency)
# Keep this <= maxconn. Default to a conservative value.
_DB_QUERY_SEMAPHORE = BoundedSemaphore(
    value=int(getattr(config, "postgres_max_concurrent_queries", 8)),
)


def _get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=1,
            # keep pool bounded; high values cause connection storms under load
            maxconn=int(getattr(config, "postgres_maxconn", 20)),
            dsn=config.psql_uri,
        )
    return _pool


def _borrow() -> tuple[SimpleConnectionPool, pg_ext.connection]:
    p = _get_pool()
    return p, p.getconn()


def _return(p: SimpleConnectionPool, conn: pg_ext.connection) -> None:
    # Always return to the same pool instance we borrowed from
    p.putconn(conn)


class _VectorAdapter:
    def __init__(self, v: list[float] | tuple[float, ...]):
        self._v = v

    def getquoted(self) -> bytes:
        inner = ",".join(repr(x) for x in self._v)
        return f"'[{inner}]'::vector".encode()


pg_ext.register_adapter(tuple, _VectorAdapter)


# +++ added: small helper for cheap Python-side RRF merge
@dataclass(frozen=True)
class _Hit:
    id: str
    text: str
    metadata: dict[str, Any] | None
    file_name: str | None


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------
class PostgresRetriever(BaseDocRetriever):
    """Postgres-backed hybrid retriever with concurrency limiting and best-effort sparse."""

    def __init__(
        self,
        retriever_top_k: int = 25,
        access_type: str = "student",
        role: str = "student",
        user_id: str = "Chat_DKU",
        search_mode: int = 0,
        files: list | None = None,
        table_name: str | None = None,
        access_table: str | None = None,
        organization: str | None = None,
        source_type: str = "doc",
        rrf_k: int = 60,
        ef_search: int = 64,
        # +++ added: DB-side timeouts (ms) and per-branch caps
        statement_timeout_ms: int | None = None,
        dense_top_k: int | None = None,
        sparse_top_k: int | None = None,
        sparse_enabled: bool = True,
        sparse_timeout_ms: int | None = None,
        verbose: bool = False,
    ):
        super().__init__(retriever_top_k, user_id, search_mode, files)
        self.exclude = set()
        self.table_name = table_name or getattr(config, "postgres_table", "chat_dku")
        # Permission schema (documents/document_access):
        # - access_table holds per-document ACL rows
        # - access_type/role default to 'student' as requested
        self.access_table = access_table or getattr(
            config, "postgres_access_table", "document_access"
        )
        self.access_type = (access_type or "student").strip()
        self.role = (role or "student").strip()
        self.organization = organization

        # Partition pruning: constrain queries to a single partition.
        # Valid values: 'doc' | 'event' (and future types).
        self.source_type = (source_type or "doc").strip()
        self.rrf_k = rrf_k
        self.ef_search = ef_search

        # If not provided, use conservative defaults that fit under your 5s outer timeout.
        self.statement_timeout_ms = (
            statement_timeout_ms
            if statement_timeout_ms is not None
            else int(getattr(config, "postgres_statement_timeout_ms", 4000))
        )
        self.sparse_timeout_ms = (
            sparse_timeout_ms
            if sparse_timeout_ms is not None
            else int(getattr(config, "postgres_sparse_timeout_ms", 1200))
        )

        # oversample branches, then fuse; helps quality while keeping final top_k stable
        self.dense_top_k = (
            dense_top_k if dense_top_k is not None else max(self.retriever_top_k, 25)
        )
        self.sparse_top_k = (
            sparse_top_k if sparse_top_k is not None else max(self.retriever_top_k, 25)
        )
        self.sparse_enabled = sparse_enabled
        self.verbose = verbose
        # print("PG RETRIEVER LOADED FROM:", __file__)
        # print("role=", self.role, "access_type=", self.access_type, "table=", self.table_name, "acl=", self.access_table)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # +++ added: cache embeddings (good for repeated queries / concurrent same query)
    @staticmethod
    @lru_cache(maxsize=2048)
    def _embed_cached(query: str) -> tuple[float, ...]:
        return tuple(Settings.embed_model.get_query_embedding(query))

    def _embed(self, query: str) -> tuple[float, ...]:
        return self._embed_cached(query)

    def _build_where(self) -> tuple[str, list]:
        """
        Build a WHERE fragment + positional params from search_mode / filters.
        Returns ("", []) when no filtering is needed.
        """
        params: list = []
        conditions: list[str] = []

        # Partition pruning (critical): must be present in WHERE.
        conditions.append("source_type = %s")
        params.append(self.source_type)

        if self.search_mode == 0:
            conditions.append("user_id = %s")
            params.append(self.user_id)

        elif self.search_mode == 1:
            conditions.append("user_id = %s")
            params.append(self.user_id)
            conditions.append("file_name = ANY(%s)")
            params.append(self.files or [])

        elif self.search_mode == 2:
            # mode 2: default corpus OR user's own files
            conditions.append(
                "(user_id = %s OR (user_id = %s AND file_name = ANY(%s)))"
            )
            params.extend([config.default_user_id, self.user_id, self.files or []])

        if self.exclude:
            conditions.append("id <> ALL(%s)")
            params.append(list(self.exclude))

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return where, params

    def _wrap_access_filter(self, where: str, params: list) -> tuple[str, list]:
        """Add ACL / permission filter based on access model.

        IMPORTANT correctness:
          - ACL must bind both doc_id AND source_type (doc_id not globally unique)
          - organization can be NULL; use IS NULL-safe comparison
        """
        org = self.organization

        # Caller-role gating rules:
        #   - public  -> can only see access_type='public'
        #   - student -> can see access_type in {'public','student'}
        #   - office  -> can only see access_type='office' (optional org match)
        # Private docs remain available to their owner (da.user_id = self.user_id),
        # independent of role.
        role_norm = (self.role or "student").strip().lower()

        allowed_parts: list[str] = []
        new_params = list(params)

        if role_norm == "public":
            allowed_parts.append("da.access_type = 'public'")
        elif role_norm == "student":
            allowed_parts.append("da.access_type = 'public'")
            allowed_parts.append("da.access_type = 'student'")
        elif role_norm == "office":
            # Office can only see office docs.
            # Keep org matching NULL-safe to align with ingestion schema.
            allowed_parts.append(
                "(da.access_type = 'office' AND ((da.organization IS NULL AND %s IS NULL) OR da.organization = %s))"
            )
            new_params.extend([org, org])
        else:
            # Unknown role: default to safest behavior (public only).
            allowed_parts.append("da.access_type = 'public'")

        # Always allow private docs for the owner.
        allowed_parts.append("(da.access_type = 'private' AND da.user_id = %s)")
        new_params.append(self.user_id)

        access_cond = (
            f"EXISTS (\n"
            f"  SELECT 1\n"
            f"  FROM {self.access_table} da\n"
            f"  WHERE da.doc_id = {self.table_name}.doc_id\n"
            f"    AND da.source_type = {self.table_name}.source_type\n"
            f"    AND (" + " OR ".join(allowed_parts) + ")\n"
            f")"
        )

        if where:
            return f"{where} AND {access_cond}", new_params
        return f"WHERE {access_cond}", new_params

    # +++ added: DB session guards
    def _apply_session_settings(self, cur, statement_timeout_ms: int) -> None:
        # DB-side timeout is critical for stability under concurrency.
        cur.execute("SET LOCAL statement_timeout = %s", (statement_timeout_ms,))
        cur.execute("SET LOCAL lock_timeout = %s", (500,))  # avoid hanging on locks
        # HNSW probe width
        cur.execute("SET LOCAL hnsw.ef_search = %s", (self.ef_search,))

    # +++ added: dense branch
    def _dense(self, conn: pg_ext.connection, query: str) -> list[_Hit]:
        embedding = self._embed(query)
        where, base_params = self._build_where()
        where, base_params = self._wrap_access_filter(where, base_params)
        sql = f"""
        SELECT id, text, metadata, file_name
        FROM   {self.table_name}
        {where}
        ORDER  BY embedding <=> (%s)::vector
        LIMIT  %s;
        """
        params = base_params + [embedding, self.dense_top_k]

        with conn.cursor() as cur:
            self._apply_session_settings(cur, self.statement_timeout_ms)
            cur.execute(sql, params)
            rows = cur.fetchall()

        hits: list[_Hit] = []
        for row in rows:
            hits.append(_Hit(id=row[0], text=row[1], metadata=row[2], file_name=row[3]))
        # debug
        # print("FINAL SQL:", sql)
        # print("PARAMS:", params)
        return hits

    # +++ added: sparse branch (can be disabled / short-timeout / best-effort)
    def _sparse(self, conn: pg_ext.connection, query: str) -> list[_Hit]:
        where, base_params = self._build_where()
        where, base_params = self._wrap_access_filter(where, base_params)
        tsquery_cond = "text_search @@ plainto_tsquery('english', %s)"
        sparse_where = (
            f"{where} AND {tsquery_cond}" if where else f"WHERE {tsquery_cond}"
        )

        sql = f"""
        SELECT id, text, metadata, file_name
        FROM   {self.table_name}
        {sparse_where}
        ORDER  BY ts_rank(text_search, plainto_tsquery('english', %s)) DESC
        LIMIT  %s;
        """
        params = base_params + [query, query, self.sparse_top_k]

        with conn.cursor() as cur:
            # give sparse a tighter timeout so it can't dominate end-to-end latency
            self._apply_session_settings(cur, self.sparse_timeout_ms)
            cur.execute(sql, params)
            rows = cur.fetchall()

        hits: list[_Hit] = []
        for row in rows:
            hits.append(_Hit(id=row[0], text=row[1], metadata=row[2], file_name=row[3]))
        return hits

    # +++ added: Python-side RRF merge (tiny compute: O(k))
    def _rrf_fuse(
        self, dense: list[_Hit], sparse: list[_Hit],
    ) -> list[tuple[_Hit, float]]:
        scores: dict[str, float] = {}
        by_id: dict[str, _Hit] = {}

        for i, h in enumerate(dense, start=1):
            by_id.setdefault(h.id, h)
            scores[h.id] = scores.get(h.id, 0.0) + 1.0 / (self.rrf_k + i)

        for i, h in enumerate(sparse, start=1):
            by_id.setdefault(h.id, h)
            scores[h.id] = scores.get(h.id, 0.0) + 1.0 / (self.rrf_k + i)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        out: list[tuple[_Hit, float]] = []
        for doc_id, sc in ranked[: self.retriever_top_k]:
            out.append((by_id[doc_id], float(sc)))
        return out

    # ------------------------------------------------------------------
    # Core query
    # ------------------------------------------------------------------
    def query(self, query: str, verbose: bool = False) -> list[NodeWithScore]:
        """
        Concurrency-safe hybrid search:
          1) Dense must succeed (fast with HNSW)
          2) Sparse is best-effort (short timeout + error suppression)
          3) Fuse with RRF in Python
        """
        t0 = perf_counter()

        # 1) semaphore wait
        t_sem0 = perf_counter()
        # Prevent connection storms / DB overload under concurrency.
        with _DB_QUERY_SEMAPHORE:
            sem_wait = perf_counter() - t_sem0

            # 2) pool wait
            t_pool0 = perf_counter()
            pool, conn = _borrow()
            pool_wait = perf_counter() - t_pool0

            try:
                # 3) dense/sparse + RRF
                t_dense0 = perf_counter()
                dense_hits = self._dense(conn, query)
                dense_s = perf_counter() - t_dense0

                sparse_hits: list[_Hit] = []
                sparse_s = 0.0
                if self.sparse_enabled:
                    t_sparse0 = perf_counter()
                    # Best-effort: sparse may timeout or error; dense still returns.
                    with suppress(Exception):
                        sparse_hits = self._sparse(conn, query)
                    sparse_s = perf_counter() - t_sparse0

                t_fuse0 = perf_counter()
                fused = self._rrf_fuse(dense_hits, sparse_hits)
                fuse_s = perf_counter() - t_fuse0

                t_commit0 = perf_counter()
                conn.commit()
                commit_s = perf_counter() - t_commit0

            except Exception:
                conn.rollback()
                raise
            finally:
                _return(pool, conn)

        total = perf_counter() - t0
        if verbose or self.verbose:
            print(
                "[pg] "
                f"sem_wait={sem_wait:.3f}s pool_wait={pool_wait:.3f}s "
                f"dense={dense_s:.3f}s sparse={sparse_s:.3f}s fuse={fuse_s:.3f}s commit={commit_s:.3f}s "
                f"total={total:.3f}s q='{query[:40]}'"
            )

        results: list[NodeWithScore] = []
        for hit, score in fused:
            md = hit.metadata or {}
            results.append(
                NodeWithScore(
                    node_id=hit.id,
                    text=hit.text,
                    metadata={
                        "file_name": hit.file_name,
                        "url": get_url(md),
                        "page_number": md.get("page_number"),
                    },
                    score=float(score),
                )
            )
        return results


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import json
    from chatdku.setup import setup

    parser = argparse.ArgumentParser(description="Test PostgresRetriever")
    parser.add_argument("--query", type=str, required=True)
    parser.add_argument("--top_k", type=int, default=5)
    parser.add_argument("--user_id", type=str, default="Chat_DKU")
    parser.add_argument("--search_mode", type=int, default=0)
    parser.add_argument("--files", nargs="*", default=None)
    parser.add_argument("--verbose", default=False, action="store_true")
    args = parser.parse_args()

    setup(use_llm=False)

    retriever = PostgresRetriever(
        retriever_top_k=args.top_k,
        user_id=args.user_id,
        search_mode=args.search_mode,
        files=args.files,
    )

    results = retriever.query(args.query)

    print("\n=== Retrieval Results ===\n")
    for i, r in enumerate(results, 1):
        print(f"Rank {i}  |  score: {r.score:.4f}  |  id: {r.node_id}")
        print("Metadata:", json.dumps(r.metadata, indent=2))
        print("Text:", r.text[:300].replace("\n", " "))
        print("-" * 60)
