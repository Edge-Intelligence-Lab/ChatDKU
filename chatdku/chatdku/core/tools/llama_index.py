from typing import Annotated, Any
from enum import Enum
from collections.abc import Iterable, Iterator, Mapping
from pydantic import Field
import os

import dspy

from contextlib import nullcontext
from openinference.instrumentation import safe_json_dumps
from opentelemetry.trace import Status, StatusCode
from openinference.semconv.trace import (
    SpanAttributes,
    DocumentAttributes,
    OpenInferenceSpanKindValues,
    OpenInferenceMimeTypeValues,
)
from opentelemetry.util.types import AttributeValue
import json
from chatdku.core.utils import truncate_tokens
from chatdku.core.dspy_common import custom_cot_rationale
import nltk
from nltk.tokenize import word_tokenize
import chromadb
import llama_index
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import TransformRetriever
from llama_index.postprocessor.colbert_rerank import ColbertRerank
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.schema import TextNode, NodeWithScore, MetadataMode
from llama_index.core.node_parser.text.token import TokenTextSplitter
from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
    FilterOperator,
)

from redis import Redis
from redis.commands.search.query import Query
from redisvl.schema import IndexSchema

import re
import string
from itertools import combinations

from chatdku.config import config


def mydeepcopy(self, memo):
    return self

ENABLE_PRINT = True

# FIXME: Ugly hack for the issue that DSPy's use of `deepcopy()` cannot copy
# certain attributes (probably due to the being Pydantic `PrivateAttr()`?)
# See: https://github.com/run-llama/llama_index/issues/14570
llama_index.vector_stores.chroma.ChromaVectorStore.__deepcopy__ = mydeepcopy

# --- Summarizer ---
# TODO: Summarizer is currently not used as it is too slow when compared to just
# simplify the metadata of the resulting nodes to fit them in the context window.
# However, they could be used IN CONJUNCTION with the technique of simplifying the
# nodes in the future and could be only called if the retrieved contexts exceeds
# certain size. Also, they could be prompted better to preserve more information
# then what they currently output.


class DocumentSummarizerSignature(dspy.Signature):
    """Update the summary with information in the documents that are relevant to the query."""

    previous_summary = dspy.InputField(
        desc="The previously generated summary of relevant information. May be empty."
    )
    documents = dspy.InputField(
        desc="The documents to extract relevant information from.",
        format=lambda x: "##########\n" + x + "\n##########",
    )
    query = dspy.InputField(desc="The query that the summary should answer.")
    current_summary = dspy.OutputField(
        desc="The combined summary of relevant information in Previous Summary and Documents.",
    )


class DocumentSummarizer(dspy.Module):
    # FIXME: We should not use fixed chunk sizes, but adjust them according to
    # the context window of the LLM and the size of the prompt.
    CHUNK_SIZE = 4096
    CHUNK_OVERLAP = 256

    def __init__(self):
        super().__init__()
        self.summarizer = dspy.ChainOfThought(
            DocumentSummarizerSignature, rationale_type=custom_cot_rationale
        )
        self.text_splitter = TokenTextSplitter(
            chunk_size=self.CHUNK_SIZE, chunk_overlap=self.CHUNK_OVERLAP
        )

    def forward(self, documents: list[NodeWithScore], query: str):
        # FIXME: This has the problem that the metadata of a document would
        # lie in only the first chunk suppose that document is split across
        # multiple chunks. However, this is how LlamaIndex's synthesizers
        # currently work (via `PromptHelper`).
        # Reference: https://github.com/run-llama/llama_index/blob/d3abf789800f4366fec7f607be15804a4a72ee52/llama-index-core/llama_index/core/indices/prompt_helper.py#L263-L280
        #
        # I recommend using `MetadataAwareTextSplitter.split_text_metadata_aware()`
        # in the future.
        texts = [node.get_content(MetadataMode.LLM) for node in documents]
        repacked = self.text_splitter.split_text("\n\n".join(texts))
        summary = ""
        for chunk in repacked:
            summary = self.summarizer(
                previous_summary=summary, documents=chunk, query=query
            ).current_summary
        return dspy.Prediction(summary=summary)


# ------------------


# FIXME: It might be necessary/safer to set a token limit in case some really
# ridiculously long nodes blow up the context window.


def get_reranker(top_n: int):
    return ColbertRerank(
        top_n=top_n,
        model="colbert-ir/colbertv2.0",
        tokenizer="colbert-ir/colbertv2.0",
        keep_retrieval_score=True,
    )


import pandas as pd
import re

df = pd.read_csv(config.url_csv_path)

# Since `file_path` is the absolute path, we only want the part beginning with "dku_website"
df["website_file_path"] = df["file_path"].str.extract(r"(dku_website/.*)")

def get_file_path(metadata):
    try:
        path = metadata["file_path"]
    except:
        path = metadata["file_directory"] + "/" + metadata["filename"]
    # if "bulletin" in path:
    #     if ENABLE_PRINT:
    #         # print(metadata)
    return path

def get_url(metadata):
    try:
        try:
            path = metadata["file_path"]
        except:
            path = metadata["file_directory"] + "/" + metadata["filename"]
        if "dku_website" in path:
            match = re.search(r"dku_website/.*", path)
            if match:
                result = match.group(0)
                matching_row = df[df["website_file_path"] == result]
                if not matching_row.empty:
                    return matching_row.iloc[0]["url"]
        else:  # pay attention, this code is only for chatdku advising
            matching_row = df[df["file_path"] == metadata["file_path"]]
            if not matching_row.empty:
                return matching_row.iloc[0]["url"]
            else:
                return "no url"
    except Exception as e:
        return f"no url, error: {str(e)}"

def get_page_number(node):
    try:
        path = node.metadata["file_path"]
        if "bulletin" in path:
            return node.metadata["page"]
        else:  # pay attention, this code is only for chatdku advising
            return "no page number"
    except:
        return "no page number"

def simplify_nodes(nodes: list[NodeWithScore]) -> NodeWithScore:
    return [
        NodeWithScore(
            node=TextNode(
                node_id=node.node_id,
                text=node.text,
                metadata={"url": get_url(node.metadata),"page_number": get_page_number(node), "file_path":get_file_path(node.metadata)},
            ),
            score=node.score,
        )
        for node in nodes
    ]


def nodes_to_string(nodes: list[NodeWithScore]):
    return "\n\n".join([node.get_content(MetadataMode.LLM) for node in nodes])


# Adapted from: https://github.com/Arize-ai/openinference/blob/a0e6f30c84011c5c743625bb69b66ba055ac17bd/python/instrumentation/openinference-instrumentation-langchain/src/openinference/instrumentation/langchain/_tracer.py#L293-L308
def _flatten(key_values: Mapping[str, Any]) -> Iterator[tuple[str, AttributeValue]]:
    for key, value in key_values.items():
        if value is None:
            continue
        if isinstance(value, Mapping):
            for sub_key, sub_value in _flatten(value):
                yield f"{key}.{sub_key}", sub_value
        elif isinstance(value, list) and any(
            isinstance(item, Mapping) for item in value
        ):
            for index, sub_mapping in enumerate(value):
                for sub_key, sub_value in _flatten(sub_mapping):
                    yield f"{key}.{index}.{sub_key}", sub_value
        else:
            if isinstance(value, Enum):
                value = value.value
            yield key, value


def nodes_to_openinference(nodes: list[NodeWithScore]) -> dict[str, Any]:
    return dict(
        _flatten(
            {
                SpanAttributes.RETRIEVAL_DOCUMENTS: [
                    {
                        DocumentAttributes.DOCUMENT_ID: node.node_id,
                        DocumentAttributes.DOCUMENT_SCORE: node.score,
                        DocumentAttributes.DOCUMENT_CONTENT: node.text,
                        **(
                            {
                                DocumentAttributes.DOCUMENT_METADATA: safe_json_dumps(
                                    metadata
                                )
                            }
                            if (metadata := node.node.metadata)
                            else {}
                        ),
                    }
                    for node in nodes
                ]
            }
        )
    )


class VectorRetriever(dspy.Module):
    """Retrieve texts from the database that are semantically similar to the query."""

    def __init__(
        self,
        retriever_top_k: int = 10,
        use_reranker: bool = False,
        reranker_top_n: int = 5,
    ):
        self.retriever_top_k = retriever_top_k
        self.use_reranker = use_reranker
        self.reranker_top_n = reranker_top_n

        db = chromadb.PersistentClient(path=config.chroma_db)
        chroma_collection = db.get_collection("dku_html_pdf")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        self.index = VectorStoreIndex.from_vector_store(vector_store)
        # self.retriever = TransformRetriever(
        #     retriever=index.as_retriever(similarity_top_k=retriever_top_k),
        #     query_transform=HyDEQueryTransform(include_original=True),
        # )
        # self.summarizer = DocumentSummarizer()

    def forward(
        self,
        query: Annotated[
            str,
            Field(
                description="Texts that might be semantically similar to the real answer to the question."
            ),
        ],
        internal_memory: dict,
    ):
        with (
            config.tracer.start_as_current_span("Vector Retriever")
            if hasattr(config, "tracer")
            else nullcontext()
        ) as span:
            exclude = list(internal_memory.get("ids", set()))
            span.set_attributes(
                {
                    SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.RETRIEVER.value,
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(
                        dict(query=query, exclude=exclude)
                    ),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            filters = MetadataFilters(
                filters=[
                    MetadataFilter(key="id", value=i, operator=FilterOperator.NE)
                    for i in exclude
                ]
            )
            retriever = self.index.as_retriever(
                similarity_top_k=self.retriever_top_k, filters=filters
            )
            # TODO: Might need to display `retrieved_nodes` in Phoenix
            retrieved_nodes = retriever.retrieve(
                # FIXME: bge-m3 has a max token limit of 8192. However, I do not know
                # what would happen if that is exceeded. Also, we should use it tokenizer
                # to get the accurate token count. This is just a temporary safety
                # measure for now.
                truncate_tokens(query, 7000)
            )

            if self.use_reranker:
                reranker = get_reranker(self.reranker_top_n)
                nodes = reranker.postprocess_nodes(
                    retrieved_nodes,
                    # BERT token limit is 512, however, we should leave some space for special tokens
                    query_str=truncate_tokens(
                        query, 500, tokenizer=reranker._tokenizer
                    ),
                )
            else:
                nodes = retrieved_nodes
            print("Vector------------------------")
            nodes = simplify_nodes(nodes)
            for node in nodes:
                if ENABLE_PRINT:
                    print(node.metadata["file_path"])
                    print(node.metadata["url"])
                    print(node.metadata["page_number"])
            result = nodes_to_string(nodes)

            span.set_attributes(nodes_to_openinference(nodes))
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(dict(result=result)),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))
            # print(result)
            return dspy.Prediction(
                result=result,
                internal_result={"ids": {r.node_id for r in nodes}},
            )

            # See notes about summarizer above
            # return dspy.Prediction(
            #     result=self.summarizer(documents=reranked_nodes, query=query).summary
            # )


class KeywordRetriever(dspy.Module):
    """Retrieve texts from the database that contain the same keywords in the query."""

    def __init__(self, retriever_top_k: int = 10, reranker_top_n: int = 3):
        self.client = Redis.from_url("redis://localhost:6379")
        self.retriever_top_k = retriever_top_k

        schema = IndexSchema.from_yaml(
            os.path.join(config.module_root_dir, "custom_schema.yaml")
        )
        self.index_name = schema.index.name

        # docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        # self.retriever = BM25Retriever.from_defaults(
        #     docstore=docstore, similarity_top_k=retriever_top_k
        # )

        # self.reranker = get_reranker(reranker_top_n)

        # self.summarizer = DocumentSummarizer()

    def forward(
        self,
        query: Annotated[
            str,
            Field(
                description="Keywords that might appear in the answer to the question."
            ),
        ],
        internal_memory: dict,
    ):
        # Escape all punctuations, e.g. "can't" -> "can\'t"
        def escape_strs(strs: list[str]):
            pattern = f"[{re.escape(string.punctuation)}]"
            return [
                re.sub(pattern, lambda match: f"\\{match.group(0)}", s) for s in strs
            ]

        with (
            config.tracer.start_as_current_span("Keyword Retriever")
            if hasattr(config, "tracer")
            else nullcontext()
        ) as span:
            exclude = list(internal_memory.get("ids", set()))
            span.set_attributes(
                {
                    SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.RETRIEVER.value,
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(
                        dict(query=query, exclude=exclude)
                    ),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            try:
                # NOTE: Just `nltk.data.find("tokenizers/punkt_tab")` won't work as LlamaIndex
                # replaces nltk tokenizers with its own version.
                nltk.data.find("tokenizers/punkt_tab/english")
            except LookupError:
                nltk.download("punkt_tab")
            # Break down the query into tokens
            tokens = word_tokenize(query)
            # Remove tokens that are PURELY punctuations
            orig_keywords = list(
                filter(lambda token: token not in string.punctuation, tokens)
            )
            orig_keywords = escape_strs(orig_keywords)

            # FIXME: Hack for improving performance with multiple keywords.
            # There ought to be better ways than this.
            # Combinations of the original keywords are generated to "boost" the result,
            # e.g. searching for "a b" would become "a OR b OR (a AND b)".
            # Without boosting, documents with a lot of either just "a" or "b" would be given
            # a heavier preferences, even though we would prefer documents with both "a" and "b".
            # Larger weights are given to combinations of larger size.
            keywords = []
            weights = []
            TUPLE_LIMIT = 4
            BOOST_FACTOR = 2
            for i in range(1, TUPLE_LIMIT + 1):
                for combo in combinations(orig_keywords, i):
                    keywords.append(" ".join(combo))
                    weights.append(BOOST_FACTOR ** (i - 1))

            # `|` means searching the union of the words/tokens.
            # `%` means fuzzy search with Levenshtein distance of 1.
            # Query attributes are used here to set the weight of the keywords.
            text_str = " | ".join(
                [
                    f"({keyword}) => {{ $weight: {weight} }}"
                    for keyword, weight in zip(keywords, weights)
                ]
            )
            query_str = "@text:(" + text_str + ")"

            exclude = escape_strs(exclude)
            exclude_str = " ".join([f"-@id:({e})" for e in exclude])
            if exclude_str:
                query_str += " " + exclude_str

            # NOTE: I think it will be better to use PARAMS for security reasons.
            # However, it appears that RediSearch has an issue using both parameters and query attributes.
            #
            # You can confirm this issue with:
            # FT.SEARCH idx:test "@text:(($keyword_0) => { $weight: 1 } | ($keyword_1) => { $weight: 1 } | ($keyword_2) => { $weight: 2 })"
            #   DIALECT 2 LIMIT 0 1 WITHSCORES EXPLAINSCORE PARAMS 6 keyword_0 "alpha" keyword_1 "beta" keyword_2 alpha beta"
            # And:
            # FT.SEARCH idx:test "@text:(($keyword_0) => { $weight: 1 } | ($keyword_1) => { $weight: 1 } | ($keyword_2) => { $weight: 2 })"
            #   DIALECT 2 LIMIT 0 1 EXPLAINSCORE PARAMS 6 keyword_0 "alpha" keyword_1 "beta" keyword_2 "alpha beta"
            #
            # Using parameters would be like this:
            # params = {f"keyword_{i}": keyword for i, keyword in enumerate(keywords)}
            # query_str = " | ".join([f"(${param}) => {{ $weight: {weight} }}" for param, weight in zip(params, weights)])
            # query_cmd = Query(query_str).dialect(2).scorer("BM25").paging(0, retriever_top_k).with_scores()
            # results = self.client.ft("idx:test").search(query_cmd, params)

            retriever_top_k = 10
            query_cmd = (
                Query(query_str).scorer("BM25").paging(0, retriever_top_k).with_scores()
            )
            results = self.client.ft(self.index_name).search(query_cmd)
            # for r in results.docs:
            #     if 'bulletin' in json.loads(r["_node_content"]).get('metadata')['file_path']:
            #         if ENABLE_PRINT:
            #             print(r)

            try:
                nodes = [
                    NodeWithScore(
                        node=TextNode(
                            id=r.id, text=r.text, metadata=json.loads(r["_node_content"]).get('metadata')
                        ),
                        score=r.score,
                    )
                    for r in results.docs
                ]
            except:
                nodes = [
                    NodeWithScore(node=TextNode(id=r.id, text=r.text), score=r.score)
                    for r in results.docs
                ]

            # retrieved_nodes = self.retriever.retrieve(query)
            # reranked_nodes = self.reranker.postprocess_nodes(
            #     retrieved_nodes,
            #     # BERT token limit is 512, however, we should leave some space for special tokens
            #     query_str=truncate_tokens(query, 500, tokenizer=self.reranker._tokenizer),
            # )
            # return dspy.Prediction(result=get_str_of_simplified_nodes(reranked_nodes))
            print("Keyword------------------------")
            nodes = simplify_nodes(nodes)
            for node in nodes:
                if ENABLE_PRINT:
                    print(node.metadata["file_path"])
                    print(node.metadata["url"])
                    print(node.metadata["page_number"])
            result = nodes_to_string(nodes)

            span.set_attributes(nodes_to_openinference(nodes))
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(dict(result=result)),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))

            # print(result)

            return dspy.Prediction(
                result=result, internal_result={"ids": {r.id for r in results.docs}}
            )

            # See notes about summarizer above
            # return dspy.Prediction(
            #     result=self.summarizer(documents=reranked_nodes, query=query).summary
            # )
