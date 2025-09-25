from typing import Annotated, Any
from enum import Enum
from collections.abc import Iterator, Mapping
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

from chatdku.core.utils import truncate_tokens
import torch
from transformers import AutoTokenizer

# import nltk
from nltk.tokenize import word_tokenize
import chromadb
from chromadb.utils.embedding_functions import HuggingFaceEmbeddingServer

# import llama_index

# from llama_index.vector_stores.chroma import ChromaVectorStore
# from llama_index.core import VectorStoreIndex
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.schema import TextNode, NodeWithScore, MetadataMode
from llama_index.core.node_parser.text.token import TokenTextSplitter


from redis import Redis
from redis.commands.search.query import Query
from redisvl.schema import IndexSchema

import re
import string
from itertools import combinations

from chatdku.config import config


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
        self.summarizer = dspy.ChainOfThought(DocumentSummarizerSignature)
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
    return SentenceTransformerRerank(
        top_n=top_n,
        model="cross-encoder/ms-marco-MiniLM-L6-v2",
        keep_retrieval_score=True,
        device=str(torch.device("cuda:0" if torch.cuda.is_available() else "cpu")),
    )


import pandas as pd

df = pd.read_csv(config.url_csv_path)
# Since `file_path` is the absolute path, we only want the part beginning with "dku_website"
df["file_path_forweb"] = df["file_path"].str.extract(r"(dku_website/.*)")


def get_url(metadata: dict):
    try:
        try:
            path = metadata["file_path"]
        except:
            path = metadata["file_directory"] + "/" + metadata["filename"]

        if "dku_website" in path:
            match = re.search(r"dku_website/.*", path)
            if match:
                result = match.group(0)
                matching_row = df[df["file_path_forweb"] == result]
                if not matching_row.empty:
                    return matching_row.iloc[0]["url"]
        else:
            matching_row = df[df["file_path"] == path]
            if not matching_row.empty:
                return matching_row.iloc[0]["url"]
        return "no url"
    except Exception as e:
        return f"no url, error: {str(e)}"


def get_page_number(metadata: dict):
    # There is no need for try statement because page_number will either
    # be a number or "Not given."
    return metadata["page_number"]


def get_file_name(metadata: dict):
    return metadata["file_name"]


def simplify_nodes(results) -> NodeWithScore:
    return [
        NodeWithScore(
            node=TextNode(
                id_=doc.id,
                text=doc.text,
                metadata={
                    "filename": os.path.basename(doc.file_path),
                    "url": get_url({"file_path": doc.file_path}),
                    "page_number": doc.page_number,
                },
            ),
            score=float(doc.score),
        )
        for doc in results.docs
    ]


def chroma_result_to_nodes(result: dict) -> NodeWithScore:
    ids = result["ids"][0]
    texts = result["documents"][0]
    metadatas = result["metadatas"][0]
    scores = result["distances"][0]

    return [
        NodeWithScore(
            node=TextNode(
                node_id=ids[i],
                text=texts[i],
                metadata={
                    "filename": get_file_name(metadatas[i]),
                    "url": get_url(metadatas[i]),
                    "page_number": get_page_number(metadatas[i]),
                },
            ),
            score=float(scores[i]),
        )
        for i in range(len(ids))
    ]


def nodes_to_dicts(nodes: list[NodeWithScore]):
    return [{"text": node.text, "metadata": node.metadata} for node in nodes]


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
                        DocumentAttributes.DOCUMENT_SCORE: float(node.score),
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
        retriever_top_k: int = 5,
        use_reranker: bool = False,
        reranker_top_n: int = 3,
    ):
        self.retriever_top_k = retriever_top_k
        self.use_reranker = use_reranker
        if self.use_reranker:
            self.reranker = get_reranker(reranker_top_n)
        else:
            self.reranker=None

        db = chromadb.HttpClient(host="localhost", port=config.chroma_db_port)
        self.collection = db.get_collection(
            name=config.chroma_collection,
            # name=config.chroma_collection,
            embedding_function=HuggingFaceEmbeddingServer(
                url=config.tei_url + "/" + config.embedding + "/embed"
            ),
        )

        # vector_store = ChromaVectorStore(chroma_collection=chatdku_collection)

        # self.index = VectorStoreIndex.from_vector_store(vector_store)
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
        user_id: str = "Chat_DKU",
        search_mode: int = 0,
        files: list = None,
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
                        dict(
                            query=query,
                            exclude=exclude,
                            user_id=user_id,
                            search_mode=search_mode,
                            files=files,
                        )
                    ),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            # Before the upgrade (just for convenience's sake)
            # filters = MetadataFilters(
            #     filters=[
            #         MetadataFilter(key="id", value=i, operator=FilterOperator.NE)
            #         for i in exclude
            #     ]
            # )

            # See https://docs.trychroma.com/docs/querying-collections/metadata-filtering
            # to understand the logic of the filters
            if search_mode == 0:
                filters = {"user_id": user_id}
                if exclude:
                    filters = {
                        "$and": [
                            {"user_id": user_id},
                            {"chunk_id": {"$nin": exclude}},
                        ]
                    }

            # search from user's files
            elif search_mode == 1:
                filters = {
                    "$and": [
                        {"user_id": user_id},
                        {"file_name": {"$in": files}},
                    ],
                }

                if exclude:
                    filters["$and"].append({"chunk_id": {"$nin": exclude}})
            elif search_mode == 2:
                filters = {
                    "$or": [
                        {
                            "$and": [
                                {"user_id": user_id},
                                {"file_name": {"$in": files}},
                            ],
                        },
                        {"user_id": "Chat_DKU"},
                    ],
                }
                if exclude:
                    filters = {
                        "$and": [
                            {
                                "$or": [
                                    {
                                        "$and": [
                                            {"user_id": user_id},
                                            {"file_name": {"$in": files}},
                                        ]
                                    },
                                    {"user_id": "Chat_DKU"},
                                ]
                            },
                            {"chunk_id": {"$nin": exclude}},
                        ]
                    }

            query_result = self.collection.query(
                # FIXME: bge-m3 has a max token limit of 8192. However, I do not know
                # what would happen if that is exceeded. Also, we should use it tokenizer
                # to get the accurate token count. This is just a temporary safety
                # measure for now.
                query_texts=truncate_tokens(query, 7000),
                n_results=self.retriever_top_k,
                where=filters,
            )

            retrieved_nodes = chroma_result_to_nodes(query_result)

            if self.use_reranker:
                tokenizer = AutoTokenizer.from_pretrained(
                    "cross-encoder/ms-marco-MiniLM-L6-v2"
                )

                nodes = self.reranker.postprocess_nodes(
                    retrieved_nodes,
                    # BERT token limit is 512, however, we should leave some space for special tokens
                    query_str=truncate_tokens(query, 500, tokenizer=tokenizer),
                )
            else:
                nodes = retrieved_nodes

            # nodes = simplify_nodes(nodes)
            result = nodes_to_dicts(nodes)

            span.set_attributes(nodes_to_openinference(nodes))
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(dict(result=result)),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))
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

    def __init__(
        self,
        retriever_top_k: int = 5,
        use_reranker: bool = False,
        reranker_top_n: int = 3,
    ):
        self.client = Redis(
            host=config.redis_host,
            port=6379,
            username="default",
            password=config.redis_password,
            db=0,
        )
        self.retriever_top_k = retriever_top_k

        schema = IndexSchema.from_yaml(
            os.path.join(config.module_root_dir, "custom_schema.yaml")
        )
        self.index_name = schema.index.name

        # docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        # self.retriever = BM25Retriever.from_defaults(
        #     docstore=docstore, similarity_top_k=retriever_top_k
        # )

        self.use_reranker = use_reranker
        if self.use_reranker:
            self.reranker = get_reranker(reranker_top_n)
        else:
            self.reranker=None

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
        user_id: str = "Chat_DKU",
        search_mode: int = 0,
        files: list = [],
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
                        dict(
                            query=query,
                            exclude=exclude,
                            user_id=user_id,
                            search_mode=search_mode,
                            files=files,
                        )
                    ),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            # try:
            #     # NOTE: Just `nltk.data.find("tokenizers/punkt_tab")` won't work as LlamaIndex
            #     # replaces nltk tokenizers with its own version.
            #     nltk.data.find("tokenizers/punkt_tab/english")
            # except LookupError:
            #     nltk.download("punkt_tab")
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

            # Adding the user_id filter if the user wants to search for
            if search_mode == 0:
                query_str = query_str + f" @user_id:{{{'Chat_DKU'}}}"

            elif search_mode == 1:
                if len(files) == 0:
                    docs_str = os.path.splitext(files[0])[0]
                else:
                    docs_str = "|".join(
                        f"{os.path.splitext(name)[0]}" for name in files
                    )

                query_str = (
                    query_str
                    + f" @user_id:{{{user_id}}} "
                    + f"@file_name:{{{docs_str}}}"
                )

            elif search_mode == 2:
                query_str = query_str + f" @user_id:{{{'Chat_DKU'}}}"
                # if len(files) == 0:
                #     docs_str = os.path.splitext(files[0])[0]
                # else:
                #     docs_str = "|".join(f"{os.path.splitext(name)[0]}" for name in files)
                #
                # user_clause = f"(@user_id:{{Chat_DKU}} | (@user_id:{{{user_id}}} @file_name:{{{docs_str}}}))"
                # query_str = query_str + f" {user_clause}"

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

            query_cmd = (
                Query(query_str)
                .scorer("BM25")
                .paging(0, self.retriever_top_k)
                .with_scores()
            )
            results = self.client.ft(self.index_name).search(query_cmd)
            retrieved_nodes = simplify_nodes(results)
            # retrieved_nodes = self.retriever.retrieve(query)
            if self.use_reranker:
                tokenizer = AutoTokenizer.from_pretrained(
                    "cross-encoder/ms-marco-MiniLM-L6-v2"
                )

                nodes = self.reranker.postprocess_nodes(
                    retrieved_nodes,
                    # BERT token limit is 512, however, we should leave some space for special tokens
                    query_str=truncate_tokens(query, 500, tokenizer=tokenizer),
                )
            else:
                nodes = retrieved_nodes

            result = nodes_to_dicts(nodes)

            span.set_attributes(nodes_to_openinference(nodes))
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(dict(result=result)),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))
            return dspy.Prediction(
                result=result, internal_result={"ids": {node.node_id for node in nodes}}
            )

            # See notes about summarizer above
            # return dspy.Prediction(
            #     result=self.summarizer(documents=reranked_nodes, query=query).summary
            # )
