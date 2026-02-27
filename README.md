# ChatDKU

ChatDKU is an agentic RAG system with a web frontend, a Flask backend, and optional Django services.
This repository is open-source and designed to run on local machines or servers.

## Quickstart (Docker)

1. Copy the environment template:
   - `cp .env.example .env`
2. Start the stack:
   - `docker compose up --build`
3. Open the app:
   - `http://localhost:3005`

To use a local secrets file without committing it, create `.env.local` and run:
```
docker compose --env-file .env.local up --build
```

## Environment Configuration

Key variables (see `.env.example`):
- Core: `LLM_API_KEY`, `LLM_BASE_URL`, `TEI_URL`, `EMBEDDING_MODEL`
- Storage: `REDIS_HOST`, `REDIS_PASSWORD`, `CHROMA_HOST`, `CHROMA_DB_PORT`
- Frontend: `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_DICTATION_WS_URL`
- Next.js server proxy: `BACKEND_INTERNAL_URL`, `BACKEND_FEEDBACK_URL`

## LLM / Embedding Services

- LLM: OpenAI-compatible server (sglang). Default guide uses port `18085`, so set `LLM_BASE_URL=http://<server-ip>:18085/v1` and `LLM_API_KEY`.
- Embedding: TEI + `bge-m3` on port `8080`, so set `TEI_URL=http://<server-ip>:8080`.
- Full server setup: see `Documentations/Deployment-Guide_ZH.md`.

## Data Ingestion (Local)

Run ingestion from `chatdku/chatdku/ingestion`:
```
python update_data.py --data_dir ./data --user_id Chat_DKU -v True
python load_chroma.py --nodes_path ./data/nodes.json --collection_name chatdku_docs
python -m chatdku.chatdku.ingestion.load_redis --nodes_path ./data/nodes.json --index_name chatdku
```

## Optional Django Stack (Docker profile)

```
docker compose --profile django up --build
```

This starts PostgreSQL, Django, and Celery in addition to the default services.

## Repository Layout

- `chatdku/`: core agent logic, ingestion, backend, and frontend
- `scraper/`: recursive web scraper
- `benchmarks/`: benchmarking scripts
- `Documentations/`: internal docs (sanitized)

## Notes

- No production data or secrets are included in this repository.
- Use `.env` or `.env.local` to provide your own credentials.
