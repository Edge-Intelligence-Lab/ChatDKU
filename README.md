# ChatDKU

## Overview

- [Core](./chatdku/core): Core agent and RAG logic. 
  - [chatdku.core.agent](chatdku/core/agent.py): The main agent class.
  - `chatdku.core.compile`: (WIP) Uses DSPy for automatic prompt optimization.
  - `chatdku.core.tools`: The vector retriever uses ChromaDB, while the keyword retriever directly uses Redis (should consider putting it into a separate module).
  - `chatdku.core.dspy_common`: Helpers for interacting with DSPy.
  - `chatdku.core.utils`: Utility functions.

- [Flask Backend](./chatdku/backend): Backend Flask apps. 
  - `backend.stt_app`: Speech-to-Text app
  - `backend.whisper_model`: Whisper API using Flask
- [Django Backend](./chatdku/django) : Django-based backend and apps
## Setup
1. SSH into our lab-server-3.
2. Install Python package virtualenv.

Create and activate the virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate # For Unix-like operating systems
.venv\bin\activate.bat    # For Windows
```

_All the following commands are assumed to be executed in the current directory (`project_root`)._

Do an editable install with pip to get the dependencies.
```bash
pip install -e .
```
3. Start the agent and talk with it:
```bash
python3 chatdku/core/agent.py
```

#### Backend Documentation
Check [`chatdku.django/`](chatdku/django) for more details
### Update Script

#### Overview

An update script update.py is provided to monitor changes in data directory and automatically update the vector store and RAG pipeline accordingly. This script detects added, modified, or removed files in the specified data directory and updates the indices and vector stores to reflect these changes.

#### Running the Update Script

To use the update script, run:
```bash
./update.py [data_dir]
```
#### How It Works

Change Detection: The script checks the current state of the data directory against a saved state (data_state.json). It identifies added, modified, and removed files and records these changes in changed_data.json.

Document Updating: Based on the detected changes, the script updates the existing documents by removing outdated entries and adding new or modified files. The updated documents are stored in new_parser_documents.pkl.

Indexing and Vector Store Update: The script rebuilds the indices and updates the vector store (both ChromaDB and Redis) to include the latest changes.

#### Important Notes

First-Time Run: If there are no existing state files in the data directory (i.e., it's the first time you run the script), the update process may take a longer time as it needs to index all files.

Redis Server: Ensure that a Redis server is running locally on port 6379, as the script uses Redis for vector storage.

# WIP: The following sections of the documentation needs update. DO NOT rely on them for now.

### Overview and Common Options

Pass in the `-h` to view all the available command line options.

The scripts need to access the embedding model via the Text Embedding Inference API,
and the LLM via an OpenAI compatible API. Therefore, you may have to specify the
following options if they differ from the default:
- `--tei-url`: Text Embedding Inference base url such as `http://localhost:8080`.
- `--llm-url`: OpenAI compatible API endpoint such as `http://localhost:8000/v1`.

`./load_and_index.py` would load data into a vector store and a document store, while
`./query.py` would query both stores for relevant information. Therefore, you can use
`-V` and `-E` to specify the location of the vector store and the document store
respectively.

To specify the embedding model and the LLM, use `-E` and `-L` respectively.

### Load and Index the Data

Run
```bash
python3 chatdku/ingestion/update-data.py --data_dir [specify-data-directory]
python3 chatdku/ingestion/load_chroma.py --nodes_path [specified-data-directory]
python3 chatdku/ingestion/load_redist.py --nodes_path [specified-data-directory]
```
and the vector-indexed nodes (chunked and metadata-attached texts) would be stored in
the Chroma DB collection `dku_html_pdf` of the vector store, and the nodes would also
be be stored in the specified document store.

### Perform RAG Queries

Before executing queries, you must load and index the data first to have a vector
store of the indexed data stored in the Chroma DB collection `dku_html_pdf` and the
document store file containing the ingested nodes. Then, you may run:
```bash
./query.py
```
This would provide an interactive interface where you can enter the query in CLI,
press `Enter`, then get the response. Use `Ctrl-D` on Linux or `Ctrl-Z` followed by
`Enter` on Windows to terminate the script.

Arize Phoenix is used for the observability/instrumentation of the RAG pipeline.
You can open the link printed in stdout during startup in your browser to see how
each stage of the RAG pipeline is run and their respective inputs/outputs. __Note:
Port collision may happen if you run multiple instances of `query.py`, which in turn
starts multiple instances of Phoenix. To avoid this issue, set a different port for
Phoenix by changing the environment variable `PHOENIX_PORT`.__


- `scraper`: The recursive web scraper Python package mostly for scraping the DKU website.
- `benchmarks`: Scripts for benchmarking and analyzing benchmark data.
- `utils`: The standable utility scripts.
