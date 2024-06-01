# LlamaIndex RAG Pipeline Functionalities Survey

## Introduction

To facilitate the comparison between different LLM RAG frameworks, I would demonstrate how different stages of an RAG pipeline implemented with [LlamaIndex](https://www.llamaindex.ai/) could be customized with example code.

## [Loading Data (Ingestion)](https://docs.llamaindex.ai/en/stable/understanding/loading/loading/#loading-data-ingestion)

### [High-Level Transformation API](https://docs.llamaindex.ai/en/stable/understanding/loading/loading/#high-level-transformation-api)

Set the transformations used with global settings or as parameters during indexing.

```python
from llama_index.core.node_parser import SentenceSplitter

text_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=10)

# global
from llama_index.core import Settings

Settings.text_splitter = text_splitter

# per-index
index = VectorStoreIndex.from_documents(
    documents, transformations=[text_splitter]
)
```

### [Ingestion Pipeline](https://docs.llamaindex.ai/en/stable/module_guides/loading/ingestion_pipeline/#ingestion-pipeline)

A `IngestionPipeline` applies a sequential list of transformations over the input
nodes, making the output of a transformation the input of the next transformation. It
could optionally be connected to a vector database where the output nodes would be
inserted into it automatically. An embeddings stage is required only when a vector
database is used.

```python
from llama_index.core import Document
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.extractors import TitleExtractor
from llama_index.core.ingestion import IngestionPipeline
from llama_index.vector_stores.qdrant import QdrantVectorStore

import qdrant_client

client = qdrant_client.QdrantClient(location=":memory:")
vector_store = QdrantVectorStore(client=client, collection_name="test_store")

pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=25, chunk_overlap=0),
        TitleExtractor(),
        OpenAIEmbedding(),
    ],
    vector_store=vector_store,
)

# Ingest directly into a vector db
pipeline.run(documents=[Document.example()])

# Create your index
from llama_index.core import VectorStoreIndex

index = VectorStoreIndex.from_vector_store(vector_store)
```

So far, specifying the transformations and inserting to a vector store could also be
done in the high-level transformation API of `VectorStoreIndex.from_documents()`.
Thus, it is the following features that make a difference:

- __Caching__: Each node + transformation combination is hashed and cached, saving
  time on subsequent runs over the same data.
    - __Local cache__:

        ```python3
        pipeline.persist("./pipeline_storage")
        new_pipeline.load("./pipeline_storage")
        ```

    - __Remote cache__:
        ```python3
        from llama_index.core.ingestion import IngestionPipeline, IngestionCache
        from llama_index.core.ingestion.cache import RedisCache


        pipeline = IngestionPipeline(
            transformations = [...],
            cache=IngestionCache(
                cache=RedisCache(
                    redis_uri="redis://127.0.0.1:6379", collection="test_cache"
                )
            ),
        )
        ```

- __Async support__: Async method `arun()`.

- __Document management__: Attaching a docstore to the ingestion pipeline will enable
  document management. For each `doc_id`, the document will be reprocessed only when
  its hash has changed. Note that `doc_id` is usually the path to each file.

    ```python3
    from llama_index.core.ingestion import IngestionPipeline
    from llama_index.core.storage.docstore import SimpleDocumentStore

    pipeline = IngestionPipeline(
        transformations=[...], docstore=SimpleDocumentStore()
    )
    ```

- __Parallel processing__: `num_workers` parameter of `run()`.

### [Node Parser Modules](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/modules/#node-parser-modules)

They can be used individually or as building blocks for a ingestion pipeline.

#### [File-Based Node Parsers](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/modules/#file-based-node-parsers)

Parse structured file formats, currently supporting HTML, Markdown, and JSON.
`SimpleFileNodeParser` would automatically determine the parser to use for the
current file type.

- Example of using `HTMLNodeParser` on the [academic calendar](https://www.dukekunshan.edu.cn/about/academic-calendar/).

```python
from llama_index.core.node_parser import HTMLNodeParser
from llama_index.readers.file import FlatReader
from pathlib import Path

docs = FlatReader().load_data(Path("index.html"))

parser = HTMLNodeParser(tags=["p", "td", "h1", "h2", "h3", "h4", "h5", "h6"])
nodes = parser.get_nodes_from_documents(docs)
```

```
{'tag': 'p', 'filename': 'index.html', 'extension': '.html'}: 2024-2025 Academic Calendar
----------------------------------------------
{'tag': 'h2', 'filename': 'index.html', 'extension': '.html'}: DKU ACADEMIC CALENDAR Academic Year 2023-2024
----------------------------------------------
{'tag': 'h4', 'filename': 'index.html', 'extension': '.html'}: Applicable to Undergraduate and Graduate ProgramsClick here to download PDF
(NOTE: CALENDAR SUBJECT TO CHANGE)
----------------------------------------------
{'tag': 'h3', 'filename': 'index.html', 'extension': '.html'}: Spring 2024
----------------------------------------------
{'tag': 'td', 'filename': 'index.html', 'extension': '.html'}: 
----------------------------------------------
{'tag': 'p', 'filename': 'index.html', 'extension': '.html'}: January 5
----------------------------------------------
{'tag': 'td', 'filename': 'index.html', 'extension': '.html'}: 
----------------------------------------------
{'tag': 'p', 'filename': 'index.html', 'extension': '.html'}: Friday at 9:00 AM. All residence halls reopen.
```

- Example of using `MarkdownNodeParser` on [RAG/README.md](https://github.com/Glitterccc/DKU_LLM/blob/main/RAG/README.md#perform-simple-rag-queries).

```python
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.readers.file import FlatReader
from pathlib import Path

docs = FlatReader().load_data(Path("./README.md"))

parser = MarkdownNodeParser()
nodes = parser.get_nodes_from_documents(docs)
```

```
{'Header_1': 'RAG Using LlamaIndex', 'Header_2': 'Usage', 'Header_3': 'Perform Simple RAG Queries', 'filename': 'README.md', 'extension': '.md'}: Perform Simple RAG Queries

Before executing queries, you must have a vector store of the indexed data. It
cannot be included in the repo as the single DB file is too large for GitHub to
store, so please refer to the previous section for loading and indexing the
data on your computer.
```

#### [Text-Splitters (Chunking)](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/modules/#text-splitters)

Changing the chunk size is mentioned as a
[basic strategy](https://docs.llamaindex.ai/en/stable/optimizing/basic_strategies/basic_strategies/#chunk-sizes)
by LlamaIndex. They have also done some
[evaluations on different chunk sizes](https://www.llamaindex.ai/blog/evaluating-the-ideal-chunk-size-for-a-rag-system-using-llamaindex-6207e5d3fec5).

- __SentenceSpliter__: Try to split text while not cutting a sentence in the middle.

    ```python
    from llama_index.core.node_parser import SentenceSplitter

    splitter = SentenceSplitter(
        chunk_size=1024,
        chunk_overlap=20,
    )
    nodes = splitter.get_nodes_from_documents(documents)
    ```

- __SentenceWindowNodeParser__: Split text into individual sentences and add
  `window_size` number of sentences before and after each sentence into its metadata.

- __SemanticSplitterNodeParser__: Proposed by [Greg Kamradt](https://youtu.be/8OJC21T2SL4?t=1933),
  it adaptively picks splitting points among sentence boundaries so that sentences with
  similar embeddings are placed in the same chunk

#### [Relation-Based Node Parsers](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/modules/#relation-based-node-parsers)

- __HierarchicalNodeParser__: Store a hierarchy of chunks of various sizes, with
  smaller chunks (children) referencing the larger chunks that contain them
  (parents). It is to be used in conjunction with `AutoMergingRetriever` so that
  when a large number of child nodes are retrieved, their parents would be returned
  instead to provide more context.

    ```python
    from llama_index.core.node_parser import HierarchicalNodeParser

    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[2048, 512, 128]
    )
    ```

### [Metadata Extraction](https://docs.llamaindex.ai/en/stable/module_guides/indexing/metadata_extraction/#metadata-extraction)

Metadata extractors use LLMs to extract contextual information from the texts and add
them to the metadata of the nodes.

There are many extractors in `llama_index.core.extractors`, I would remark on two of
them:

- __QuestionsAnsweredExtractor__: Let an LLM come up with the questions that the text
  in this node could potentially answer. This is helpful as that questions are
  usually used as the query input.

- __EntityExtractor__: Extract named entities such as people and places. This
  involves the use of a specialized named entity cognition model, with the default
  being [tomaarsen/span-marker-mbert-base-multinerd](https://huggingface.co/tomaarsen/span-marker-mbert-base-multinerd).

Custom extractors can be defined by inheriting `BaseExtractor`. However, to extract
metadata that fits a custom schema, a Pydantic model describing the schema should be
used. While LlamaIndex provides integration with Marvin, Marvin only supports OpenAI
models and would not be suitable for the goal of running the entire model locally.

Thus, `PydanticProgramExtractor` would be the preferred choice in this case. To use
it, a Pydantic program, which calls the LLM and returns a Pydantic model, is needed.
There exists a few choices:

- __LLMTextCompletionProgram__: Give the LLM the instruction to structure its output
  that conforms to a certain format and extract the Pydantic object from the output.
  However, as the LLM is only prompted and not forced to output in a certain way, it
  would be possible that some output does not conform to the specification. I am not
  sure about how these cases are handled.

    ```python
    class Song(BaseModel):
        """Data model for a song."""

        title: str
        length_seconds: int


    class Album(BaseModel):
        """Data model for an album."""

        name: str
        artist: str
        songs: List[Song]

    from llama_index.core.program import LLMTextCompletionProgram

    prompt_template_str = """\
    Generate an example album, with an artist and a list of songs. \
    Using the movie {movie_name} as inspiration.\
    """
    program = LLMTextCompletionProgram.from_defaults(
        output_cls=Album,
        prompt_template_str=prompt_template_str,
        verbose=True,
    )
    ```

- __FunctionCallingProgram__: For LLMs that support function calling, uses such
  capability to force their output to conform to the Pydantic specification. This
  would not work with Llama 3 as it does not support function calling.

- __GuidancePydanticProgram__: This guarantees the validity of the output via
  [Guidance](https://github.com/microsoft/guidance).

    ```python
    from pydantic import BaseModel
    from typing import List
    from guidance.llms import OpenAI

    from llama_index.program.guidance import GuidancePydanticProgram

    program = GuidancePydanticProgram(
        output_cls=Album,
        prompt_template_str=(
            "Generate an example album, with an artist and a list of songs. Using"
            " the movie {{movie_name}} as inspiration"
        ),
        guidance_llm=OpenAI("text-davinci-003"),
        verbose=True,
    )
    ```

## Retrieve

1. Recursive Retrieve
2. Hybrid Retieve
3. Re-ranking
4. Meta-data Filtering

## Prompt

1. Prompt compression
2. context locations

## Evaluation

1. Relevancy
2. Faithfulness
