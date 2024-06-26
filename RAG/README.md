# RAG Using LlamaIndex

## Usage

### Prerequisites For RAG Scripts

Install system dependencies for the `unstructured` reader: `libmagic-dev`,
`poppler-utils`, and `tesseract-ocr`. For Debian based OSes, simply run:
```bash
sudo apt install libmagic-dev poppler-utils tesseract-ocr
```

Install Python 3.9 or above; install Python package virtualenv.

Create and activate the virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate # For Unix-like operating systems
.venv\bin\activate.bat    # For Windows
```

Do an editable install with pip to get the dependencies. The follow example sets the
appropriate variables to enable CUDA for llama.cpp. `CUDA_VISIBLE_DEVICES` should
correspond to your GPU setup. The example lets llama.cpp use the first two GPUs.
```bash
CUDA_VISIBLE_DEVICES=0,1 CMAKE_ARGS="-DLLAMA_CUDA=on" FORCE_CMAKE=1 pip install -e .
```

Download an LLM such as
[Llama 3 8B Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct).
Currently, only the support for Llama 3 is guaranteed.  To download a model from
Hugging Face, you can use `huggingface-cli`, alternatively, use `git clone` with
`git-lfs` installed.

These scripts uses [llama.cpp](https://github.com/ggerganov/llama.cpp), thus, the
model has to be in GGUF format. For example, to convert a Llama 3 downloaded from
Hugging Face to GGUF, you should run the following
```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
pip3.11 install -r requirements.txt  #Tip: "AttributeError: module 'pkgutil' has no attribute 'ImpImporter'" the error exists for python 3.12, so pip3.11 is required temporarily.
python3 convert-hf-to-gguf.py [path_to_your_downloaded_model] --outfile [path_to_output_file.gguf] --outtype q8_0
```
Note that `--outtype` specifies the quantization type and 8-bit quantization is used
in this case.


### Load and Index the Data

Run
```bash
./load_and_index.py \
    --e [huggingface_embedding_model_name] (optional: use a small embedding model by default) \
    --l [path_to_your_llm.gguf] (optional: not using LLM by default)
```
and the vector store of the indexed data would be placed in the `Chroma DB`
collection `dku_html_pdf` stored in database `./chroma_db`.

### Perform RAG Queries

Before executing queries, you must have a vector store of the indexed data. It
cannot be included in the repo as the single DB file is too large for GitHub to
store, so please refer to the previous section for loading and indexing the
data on your computer.

With a `Chroma DB` database stored in `./chroma_db` and the vector store of the data
in the collection `dku_html_pdf`, run:
```bash
./query.py \
    --e [huggingface_embedding_model_name] (optional: use a small embedding model by default) \
    --l [path_to_your_llm.gguf] (optional: not using LLM by default)
```
This would provide an interactive interface where you can enter the query in CLI,
press `Enter`, then get the response. Use `Ctrl-D` on Linux or `Ctrl-Z` followed by
`Enter` on Windows to terminate the script.

Arize Phoenix is used for the observability/instrumentation of the RAG pipeline.
You can open the link printed in stdout during startup in your browser to see how
each stage of the RAG pipeline is run and their respective inputs/outputs.

### Utility for Counting and Get Size of Data Files by Extension

Run
```bash
./data_count_size.sh
```
to count the number of files and their total sizes grouped by their extensions in
`../RAG_data`.

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

## Possible TODOs

- Better integration with the LLM.
  [LLM could be used at multiple stages:](https://docs.llamaindex.ai/en/stable/understanding/using_llms/using_llms/)
    - Indexing: Determine the relevance of the data.
    - Retrieval: Query different indices.
    - Response synthesis: Combine query answers to a coherent response.
- Use a better embedding model.
- Improve data reading.
    - Special techniques should be used to handle, for example, PDF map files as
      they have spatial and graphical information in addition to the text.
- Customize how the documents are transformed/partitioned.
    - The structure of the documents might need to be preserved in ways such as
      adding emphasis to the headings (similar to converting HTML to Markdown and
      have \# for headings that the LLM might pick up), including a table of contents,
      summarize the chapters and sections, and etc.
- Customize the query engine/add a querying pipeline.



# Auto-Retrieval Example for Duke Kunshan University

This project demonstrates how to perform auto-retrieval from a vector database using LlamaIndex and Chroma. The sample data used is based on the introduction and key aspects of Duke Kunshan University (DKU).

