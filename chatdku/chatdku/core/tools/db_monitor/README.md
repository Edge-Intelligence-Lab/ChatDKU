# db_monitor Module

A unified database query monitoring and reporting subsystem for ChatDKU. This module provides **query-level observability** for retrieval infrastructure (currently ChromaDB and Redis), including logging, aggregation, reporting, and automated jobs.

The design goal is to make RAG database behavior **auditable, comparable, and production-debuggable** without coupling monitoring logic to the retriever or agent layer.

---

## 1. What This Module Does

The `db_monitor` module:

- Records **error database query** (vector or keyword)
- Tracks latency, result counts, partial results, and failure modes
- Aggregates statistics over time windows
- Generates **human-readable** and **machine-readable** reports
- Supports **CLI inspection**, **scheduled jobs**, and **programmatic access**

It is intended for:

- RAG performance debugging
- Vector DB vs keyword DB comparison
- Detecting partial / empty retrievals
- Ops-level monitoring (latency spikes, Redis hanging, error rates)

---

## 2. Directory Structure Overview

```
db_monitor/
├── db_monitor.py            # Core monitor, data model, aggregation logic
│
├── cli/
│   └── report.py            # Standalone CLI report generator
│
├── report/
│   └── text.py              # Text report formatting utilities
│
├── jobs/
│   └── daily_report.py      # Scheduled / cron-style reporting job
│
├── redis_monitor/
│   ├── redis_listener.py    # Hooks into Redis queries
│   └── redis_hanging_detector.py  # Detects stuck / hanging Redis calls
```

---

## 3. Core Module: `db_monitor.py`

### Responsibilities

- Defines the **QueryRecord** schema
- Persists query logs to a local SQLite database
- Aggregates statistics across time windows
- Exposes a clean API for querying metrics

### Key Concepts

Each recorded query typically includes:

- `db_type`: `chroma` or `redis`
- `query_type`: `vector` or `keyword`
- `latency_ms`
- `result_count`
- `requested_k` (if applicable)
- `outcome`:
  - `success`
  - `empty_result`
  - `partial_result`
  - `timeout`
  - `connection_error`
  - `query_error`

### Public API (Conceptual)

```python
monitor = get_query_monitor()

stats = monitor.get_stats_from_db(
    hours=24,
    query_type="vector",
    db_type=DatabaseType.CHROMA
)
```

Returned statistics include:

- Total queries
- Error / partial rates
- Latency distribution (avg / min / max)
- Result fulfillment rate
- Outcome distribution
- Per-database breakdown

---

## 4. Text Report Formatter: `report/text.py`

This module converts raw statistics into **human-readable terminal reports**.

### Features

- Outcome indicators
- Per-database breakdown
- Recent query samples

It is intentionally **pure formatting logic**:

- No DB access
- No side effects
- Reusable by CLI, jobs, or email

---

## 5. CLI Report Tool: `cli/report.py`

A standalone command-line interface for generating reports.

### Purpose

- Inspect DB behavior without running the agent
- Debug retrieval issues in production
- Export reports for offline analysis

### Usage

```bash
python -m report
```

Common options:

```bash
python -m report --hours 48
python -m report --db chroma
python -m report --db redis
python -m report --compare
python -m report --json
python -m report --export report.txt
```

### Supported Modes

- **Text report** (default)
- **JSON output** (for dashboards / scripts)
- **Side-by-side comparison** (ChromaDB vs Redis)

### What the CLI Does *Not* Do

- It does **not** send emails
- It does **not** schedule jobs
- It does **not** trigger monitoring

It is a **read-only consumer** of recorded data.

---

## 6. Scheduled Jobs: `jobs/daily_report.py`

This module is intended for:

- Cron jobs
- Systemd timers
- Background schedulers

Typical responsibilities:

- Generate daily or weekly summaries
- Optionally send reports via email / webhook
- Detect anomalies (high error rate, latency spikes)

The job **reuses the same monitor + report utilities** as the CLI.

---

## 7. Redis Monitoring Subsystem: `redis_monitor/`

### `redis_listener.py`

- Hooks into Redis query execution
- Detect abnoral key deletion
- Detect server disconnection
- Send alert email

### `redis_hanging_detector.py`

- Detects Redis calls exceeding a timeout threshold
- Flags hanging connections
- Prevents silent deadlocks in retrieval

This layer is Redis-specific and isolated by design.

---

## 8. Data Storage

`PATH = "/datapool/db_listener/db_query_metrics.db"`

- Backed by a **local SQLite database**
- Path defined by `DEFAULT_DB_PATH`
- Automatically created when monitoring starts

If the DB file does not exist, the CLI will fail with:

```
Database not found: <path>
```

---

## 9. Typical Workflows

### A. Debug Retrieval Quality

1. Run system under normal load
2. Generate report:
   ```bash
   python -m report --hours 24
   ```
3. Inspect:
   - Empty / partial result rates
   - Result fulfillment

### B. Compare Vector vs Keyword Search
 
```bash
python -m report --compare
```

Use this to justify:

- Hybrid retrieval
- top_k tuning
- DB-level routing decisions

### C. Ops Monitoring

- Schedule `daily_report.py`
- Alert on:
  - High error rate
  - High latency
  - Redis hanging events

---

## 10. Design Principles

- **Read-only reporting** separated from write-path monitoring
- **DB-agnostic aggregation**, DB-specific listeners
- **Single source of truth** for query logs
- CLI, jobs, and future dashboards all consume the same core API

---

## 11. Extension Points

- Add new DB types (e.g. Milvus, Weaviate)
- Add Prometheus exporter
- Add email / Slack adapters
- Add long-term retention / rollups

---

## 12. Summary

The `db_monitor` module provides production-grade visibility into RAG database behavior.

- `db_monitor.py`: core data + aggregation
- `report/`: formatting
- `cli/`: human-facing inspection
- `jobs/`: automation
- `redis_monitor/`: DB-specific instrumentation

It is safe to use in production and intentionally decoupled from the agent layer.

