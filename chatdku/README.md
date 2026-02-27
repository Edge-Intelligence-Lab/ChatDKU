# ChatDKU

## Overview

- `chatdku.core`: Core agent and RAG logic. [Core](./chatdku/core)
  - `chatdku.core.agent`: The main agent logic. You can directly execute it for a simple CLI that asks you for a query and gives a response.
  - `chatdku.core.compile`: (WIP) Uses DSPy for automatic prompt optimization.
  - `chatdku.core.llamaindex_tools`: The vector retriever uses LlamaIndex and ChromaDB, while the keyword retriever directly uses Redis (should consider putting it into a separate module).
  - `chatdku.core.dspy_common`: Helpers for interacting with DSPy.
  - `chatdku.core.dspy_patch`: Patches the internals of DSPy to adapt it to our project.
  - `chatdku.core.utils`: Utility functions.

- `chatdku/frontend`: The HTML, CSS, and JavaScript web frontend. [Frontend](./chatdku/frontend)

- `chatdku.backend`: Backend Flask apps. [Flask Backend](./chatdku/backend)
  - `backend.stt_app`: Speech-to-Text app
  - `backend.whisper_model`: Whisper API using Flask
- `chatdku.django`: Django-based backend and apps[Django Backend](./chatdku/django) 
## Setup

### Embedding Model and LLM

The RAG scripts require an embedding model hosted on a
[Text Embeddings Inference](https://github.com/huggingface/text-embeddings-inference)
server and an LLM server with OpenAI compatible API. You can skip this section if you
already have them set up.

To host an embedding model, first install
[Text Embeddings Inference](https://github.com/huggingface/text-embeddings-inference).
Then, you should run each embedding model as a separate TEI docker container, and
[setup nginx routing for multiple model endpoints](https://github.com/huggingface/text-embeddings-inference/issues/256#issuecomment-2173645910).
The endpoints should be of the format `[base_url]/[author]/[model_name]/embed`, e.g.
`http://127.0.0.1:8080/BAAI/bge-m3/embed`.

To host an LLM server with OpenAI compatible API, one option is vLLM. You can follow
the tutorials below to set it up:
- [Installation](https://docs.vllm.ai/en/stable/getting_started/installation.html)
- [Run an OpenAI compatible server](https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html)
- [Setup with multiple GPUs](https://docs.vllm.ai/en/stable/serving/distributed_serving.html)

### `chatdku.ingestion` Dependencies

Install system dependencies for the `unstructured` reader: `libmagic-dev`,
`poppler-utils`, and `tesseract-ocr`. For Debian based OSes, simply run:
```bash
sudo apt install libmagic-dev poppler-utils tesseract-ocr
```

## Usage

Install Python 3.11 or above; install Python package virtualenv.

Create and activate the virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate # For Unix-like operating systems
.venv\bin\activate.bat    # For Windows
```

_All the following commands are assumed to be executed in the current directory (`project_root/chatdku`)._

Do an editable install with pip to get the dependencies.
```bash
pip install -e .
```

For the sake of easy monitoring and long-term running, the commands will all be executed with "nohup".

### Frontend

First, we need to turn this folder into a Python server so that users can see the index.html file when they access the corresponding port.
```bash
nohup python -u -m http.server 9014 -d chatdku/frontend > ./logs/python_server_logs.txt &
disown -h
```

### Main Backend

Set the Phoenix authentication token in the environment variable:
```bash
export OTEL_EXPORTER_OTLP_HEADERS='Authorization=Bearer <token>'
```
_This is considered [unsecure](https://github.com/Glitterccc/ChatDKU/issues/15), but only a temporary convenience during development._

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
- `--llm-url`: OpenAI compatible API endpoint such as `http://localhost:18085/v1`.

`./load_and_index.py` would load data into a vector store and a document store, while
`./query.py` would query both stores for relevant information. Therefore, you can use
`-V` and `-E` to specify the location of the vector store and the document store
respectively.

To specify the embedding model and the LLM, use `-E` and `-L` respectively.

### Load and Index the Data

Run
```bash
./load_and_index.py
```
and the vector-indexed nodes (chunked and metadata-attached texts) would be stored in
the Chroma DB collection `dku_html_pdf` of the vector store, and the nodes would also
be be stored in the specified document store.

Use `-d` to specify the directory to load data from.

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

## About

This is a minimal working RAG pipeline using [LlamaIndex](https://www.llamaindex.ai/)
and Llama 3. It provides the functionality of loading and indexing the
original data, storing them in a `Chroma DB` vector database, and querying the
relevant information in the database to synthesize the response.

The [unstructured](https://github.com/Unstructured-IO/unstructured) data preprocessing
library is used for reading data from HTML (including .htm) and PDF files. Only these
two file formats are considered as the remaining data are just a few images that do
not provide much information. (I believe there might also be some DOC files on DKU
website, but the crawler might encountered some network issues at the time of
crawling.) Using `unstructured` is preferred over the default document reader as:
- It parses the HTML files to extract their text instead of adding the entire
  file.
- It provides advanced processing functionalities for PDF files such as OCR,
      though I did not use these functions yet.

The `UnstructuredReader` provided by LlamaIndex has a issue with HTML files
containing large amounts of JavaScript, which would have their file types misidentified
by `unstructured.partition.auto.partion` as code and treated as plain text.
Therefore, `unstructured.file_utils.filetype.detect_filetype` has been overridden
with a custom function to mitigate this issue.

I currently use a tiny embedding model (`bge-small-en-v1.5`) grabbed from the MTEB
Leaderboard so that my VRAM would not explode.
