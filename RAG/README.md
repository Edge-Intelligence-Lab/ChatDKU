# RAG Using LlamaIndex

## Usage

### Prerequisites For RAG Scripts

Install Python 3.8 or above; install Python package virtualenv.

Create and activate the virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate # For Unix-like operating systems
.venv\bin\activate.bat    # For Windows
```

Do an editable install with pip to get the dependencies.
```bash
pip install -e .
```

### Load and Index the Data

Run
```bash
./load_and_index.py
```
and the vector store of the indexed data would be placed in the `Chroma DB`
collection `dku_html_pdf` stored in database `./chroma_db`.

### Perform Simple RAG Queries

Before executing queries, you must have a vector store of the indexed data. It
cannot be included in the repo as the single DB file is too large for GitHub to
store, so please refer to the previous section for loading and indexing the
data on your computer.

With a `Chroma DB` database stored in `./chroma_db` and the vector store of the data
in the collection `dku_html_pdf`, run:
```bash
./query_simple.py
```
This would provide an interactive interface where you can enter the query in CLI,
press `Enter`, then get the response. Use `Ctrl-D` on Linux or `Ctrl-Z` followed by
`Enter` on Windows to terminate the script.

### Utility for Counting and Get Size of Data Files by Extension

Run
```bash
./data_count_size.sh
```
to count the number of files and their total sizes grouped by their extensions in
`../RAG_data`.

## About

This is a minimum working example of using `LlamaIndex` to provide the "retrieval"
part of the RAG pipeline. It provides the functionality of loading and indexing the
original data, storing them in a `Chroma DB` vector database, and querying the
relevant information in the database.

The `unstructured` data preprocessing library is used for reading data from HTML
(including .htm) and PDF files. Only these two file formats are considered as the
remaining data are just a few images that do not provide much information. (I believe
there might also be some DOC files on DKU website, but the crawler might encountered
some network issues at the time of crawling.) Using `unstructured` is preferred over
the default document reader as:
- It parses the HTML files to extract their text instead of adding the entire
  file.
- It provides advanced processing functionalities for PDF files such as OCR,
      though I did not use these functions yet.

A custom reader using the `unstructured` library is used as opposed to the
`UnstructuredReader` provided by LlamaIndex as it has a issue with HTML files
containing large amounts of JavaScript, which would have their file types misidentified
by `unstructured.partition.auto.partion` used in the origin implementation.

I currently use a tiny embedding model (`bge-small-en-v1.5`) grabbed from the MTEB
Leaderboard so that my VRAM would not explode.

LLM is not included yet and only the retrieval function is demonstrated.

## Possible TODOs

- Add an LLM.
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
