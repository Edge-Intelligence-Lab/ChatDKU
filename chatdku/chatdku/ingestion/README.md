# Ingestion Pipeline
The ChatDKU ingestion workflow converts raw files (PDF/HTML/CSV/XLSX/etc.) into searchable vector data for both Redis and ChromaDB.
The full pipeline consists of two major stages:

1. Data Synchronization (update_data.py)
- Detect changes in the data directory (added/removed files)
- Parse new files into TextNodes
- Update nodes.json and log.json
- Output is a clean, complete set of nodes ready for embedding

2. Vector Indexing  

You may load the processed nodes into either or both vector stores:
- ChromaDB: Local persistent vector store used for keyword + vector hybrid search
- Redis (RediSearch + Vectors): In-memory vector index used for fast runtime retrieval

Both loaders operate on the same nodes.json and follow the same ingestion pattern.

## update_data.py

### Purpose
`update_data` provides **automatic incremental updates** for a data directory. It:

- Detects newly added and deleted files  
- Parses new files into TextNodes (PDF / HTML / CSV / XLSX / etc.)  
- Removes nodes belonging to deleted files from `nodes.json`  
- Updates `log.json` to reflect the current file state  

This keeps `nodes.json` fully synchronized with `data_dir` for vector-store construction or retrieval.

### Core Structure
- **read_changes** — Compare `data_dir` with `log.json` to detect added/removed files  
- **_read_pdf / _read_non_pdf** — Parse files and convert them into nodes  
- **_import_data / _write_data** — Read/write `nodes.json`  
- **write_changes** — Update `log.json`  
- **update** — Main incremental-update pipeline  
- **main** — CLI entry point  

### How to Run
```bash 
python update_data.py --data_dir /path/to/data --user_id Chat_DKU -v True
```
After running, the module automatically updates:
- nodes.json (all parsed nodes)
- log.json (current processed file list)

## load_chroma.py

This module populates a ChromaDB collection using nodes stored in a `nodes.json` file.  
It is typically used after running your data ingestion pipeline (e.g., `update_data.py`) to index parsed documents in a vector database.

### Basic Usage

1. Load into the Default Collection (Production)
If you want to overwrite the default production collection:

```bash
python load_chroma.py
```
This will:
- Read from config.nodes_path
- Load into config.chroma_collection
- Reset the existing collection (reset=True by default)  

**Do not use this default mode when testing.**

2. Usage for Testing **(Recommended)**  
When testing, you must avoid overwriting the main production vector store.
Always provide your own test nodes path and a test collection name.

Example:
```bash
python load_chroma.py \
  --nodes_path /path/to/test/nodes.json \
  --collection_name test_collection
```
This ensures that your test data goes into a separate collection and does not interfere with the production index.

### Output 
When completed, the script prints:
`Chroma load done!`

## load_redis.py

### Purpose
`redis_loader` populates a Redis vector index using **TextNodes parsed from nodes.json**. It supports:

- Loading nodes from a file or directly from a list  
- Cleaning metadata (e.g., normalizing file names)  
- Creating a custom Redis index schema  
- Writing embeddings and metadata into Redis via LlamaIndex  
- Optional full reset of existing Redis data  

This provides the vector-search backend for course planning and other retrieval features.

### Core Structure
- **clean_file_name** — Normalize file names before indexing  
- **load_redis** — Main ingestion pipeline  
  - Load nodes → clean metadata  
  - Build index schema  
  - Initialize RedisVectorStore  
  - Run ingestion pipeline with embeddings  

### Basic Usage

1. Load into the Default Index (Production)
If you want to **overwrite the default production** collection:

```bash
python -m chatdku.chatdku.ingestion.load_redis
```
This will:
- Read from config.nodes_path
- Load into config.index_name

**Do not use this default mode when testing.**

2. Usage for Testing (**Recommended**)  
When testing, you must **avoid overwriting the main production vector store.**
Always **provide your own test nodes path and a test collection name.**

Example:
```bash
python -m chatdku.chatdku.ingestion.load_redis \
    --nodes_path /path/to/nodes.json \
    --index_name test_index \
    --reset False
```
This ensures that your test data goes into a separate collection and does not interfere with the production index.

### Output 
When completed, the script prints:
`Redis load done!`
