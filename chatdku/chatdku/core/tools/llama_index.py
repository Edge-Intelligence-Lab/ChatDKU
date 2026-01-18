import os
import re
import signal
import string
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, nullcontext
from enum import Enum
from itertools import combinations
from typing import Any

import chromadb
import pandas as pd
from chromadb.utils.embedding_functions import HuggingFaceEmbeddingServer
from llama_index.core.schema import NodeWithScore, TextNode
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    DocumentAttributes,
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode
from opentelemetry.util.types import AttributeValue
from redis import Redis
from redis.commands.search.query import Query
from redisvl.schema import IndexSchema

from chatdku.config import config
from chatdku.core.utils import truncate_tokens

# ------------------


# def get_reranker(top_n: int):
#     return SentenceTransformerRerank(
#         top_n=top_n,
#         model="cross-encoder/ms-marco-MiniLM-L6-v2",
#         keep_retrieval_score=True,
#         device=str(torch.device("cuda:0" if torch.cuda.is_available() else "cpu")),
#     )


class QueryTimeoutError(Exception):
    """Raised when a query exceeds the timeout limit."""

    pass


@contextmanager
def timeout(seconds: int = 5):
    """Context manager for timing out operations."""

    def timeout_handler(signum, frame):
        raise QueryTimeoutError(f"Query exceeded {seconds} second timeout")

    # Set the signal handler and alarm
    original_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        # Restore original handler and cancel alarm
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)


def get_url(metadata: dict):
    df = pd.read_csv(config.url_csv_path)
    # Since `file_path` is the absolute path, we only want the part beginning with "dku_website"
    df["file_path_forweb"] = df["file_path"].str.extract(r"(dku_website/.*)")

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


def simplify_nodes(results) -> list[NodeWithScore]:
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


def nodes_to_dicts(nodes: list[NodeWithScore]) -> list:
    return [{"text": node.text, "metadata": node.metadata} for node in nodes]


# Adapted from: https://github.com/Arize-ai/openinference/blob/a0e6f30c84011c5c743625bb69b66ba055ac17bd/python/instrumentation/openinference-instrumentation-langchain/src/openinference/instrumentation/langchain/_tracer.py#L293-L308
def _flatten(
    key_values: Mapping[str, Any],
) -> Iterator[tuple[str, AttributeValue]]:

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


def __get_chroma_filter(
    search_mode: int,
    user_id: str,
    exclude: list,
    files: list,
) -> dict:
    """
    Read the following to understand the logic of the filters:
    https://docs.trychroma.com/docs/querying-collections/metadata-filtering
    """
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
    return filters


def DocRetrieverOuter(
    internal_memory: dict,
    retriever_top_k: int = 5,
    use_reranker: bool = False,
    reranker_top_n: int = 3,
    user_id: str = "Chat_DKU",
    search_mode: int = 0,
    files: list = [],
):

    def __VectorRetriever(
        query: str,
    ) -> list:
        """
        Retrieve texts from the database that are
        semantically similar to the query.
        """
        db = chromadb.HttpClient(host="localhost", port=config.chroma_db_port)
        collection = db.get_collection(
            name=config.chroma_collection,
            embedding_function=HuggingFaceEmbeddingServer(
                url=config.tei_url + "/" + config.embedding + "/embed"
            ),
        )
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
            filters = __get_chroma_filter(
                search_mode,
                user_id,
                exclude,
                files,
            )

            query_result = collection.query(
                query_texts=truncate_tokens(query, 7000),
                n_results=retriever_top_k,
                where=filters,
            )

            retrieved_nodes = chroma_result_to_nodes(query_result)

            span.set_attributes(nodes_to_openinference(retrieved_nodes))
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                        dict(result=retrieved_nodes)
                    ),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))
        return retrieved_nodes

    def __KeywordRetriever(
        query: str | list[str],
    ) -> list:
        """
        Retrieve texts from the database that contain the
        same keywords in the query.
        """
        client = Redis(
            host=config.redis_host,
            port=6379,
            username="default",
            password=config.redis_password,
            db=0,
        )

        schema = IndexSchema.from_yaml(
            os.path.join(config.module_root_dir, "custom_schema.yaml")
        )
        index_name = schema.index.name

        # Escape all punctuations, e.g. "can't" -> "can\'t"
        def _escape_strs(strs: list[str]):
            if strs:
                pattern = f"[{re.escape(string.punctuation)}]"
                return [
                    re.sub(pattern, lambda match: f"\\{match.group(0)}", s)
                    for s in strs
                ]
            else:
                return []

        def _extract_keywords(query):
            tokens = word_tokenize(query.lower())
            stop_words = set(stopwords.words("english"))
            # Keep tokens that are not stopwords and not pure punctuation
            keywords = [
                t
                for t in tokens
                if t not in stop_words and t not in string.punctuation and len(t) > 1
            ]
            return keywords

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

            if isinstance(query, str):
                # try:
                #     # NOTE: Just `nltk.data.find("tokenizers/punkt_tab")`
                #     # won't work as LlamaIndex
                #     # replaces nltk tokenizers with its own version.
                #     nltk.data.find("tokenizers/punkt_tab/english")
                # except LookupError:
                #     nltk.download("punkt_tab")

                # Break down the query into tokens
                tokens = _extract_keywords(query)
                # Remove tokens that are PURELY punctuations
                orig_keywords = _escape_strs(tokens)

                # FIXME: Hack for improving performance with multiple keywords.
                # There ought to be better ways than this.
                # Combinations of the original keywords are generated to "boost" the result,
                # e.g. searching for "a b" would become "a OR b OR (a AND b)".
                # Without boosting, documents with a lot of either just "a" or "b" would be given
                # a heavier preferences, even though we would prefer documents with both "a" and "b".
                # Larger weights are given to combinations of larger size.
                keywords = []
                weights = []
                # Changed this to 2 from 4
                # See issue #152
                TUPLE_LIMIT = 2
                BOOST_FACTOR = 2
                for i in range(1, TUPLE_LIMIT + 1):
                    for combo in combinations(orig_keywords, i):
                        keywords.append(" ".join(combo))
                        weights.append(BOOST_FACTOR ** (i - 1))

                # Trying to preserve the original keyword combination too
                if len(orig_keywords) > 2:
                    keywords.append(" ".join(orig_keywords))
                    weights.append(BOOST_FACTOR ** (TUPLE_LIMIT + 1))

                # `|` means searching the union of the words/tokens.
                # `%` means fuzzy search with Levenshtein distance of 1.
                # Query attributes are used here to set the weight of the keywords.
                text_str = " | ".join(
                    [
                        f"({keyword}) => {{ $weight: {weight} }}"
                        for keyword, weight in zip(keywords, weights)
                    ]
                )
            elif isinstance(query, list):
                text_str = " | ".join(query)

            query_str = "@text:(" + text_str + ")"

            exclude = _escape_strs(exclude)
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
                .dialect(2)
                .scorer("BM25")
                .paging(0, retriever_top_k)
                .with_scores()
            )

            results = client.ft(index_name).search(query_cmd)
            retrieved_nodes = simplify_nodes(results)

            span.set_attributes(nodes_to_openinference(retrieved_nodes))
            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                        dict(result=retrieved_nodes)
                    ),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))
        return retrieved_nodes

    def DocumentRetriever(
        semantic_query: str,
        keyword_query: str | list[str],
    ) -> tuple[list, dict]:
        """
        Retrieve relevant documents using hybrid search (semantic + keyword matching).

        Combines vector similarity search with BM25 keyword ranking to find the most
        relevant documents. Use semantic_query for conceptual searches and keyword_query
        for exact term matching.

        Args:
            semantic_query: Natural language query for semantic/conceptual search
            keyword_query: Specific terms or phrases for BM25 keyword matching.
                Can be a string or list of strings.
            timeout_seconds: Maximum time allowed for query execution (default: 5)

        Returns:
            Tuple of (matched_documents_list, internal_result_dict)
            Returns ([], {}) if query times out or fails
        """
        try:
            if isinstance(keyword_query, list):
                for i in range(len(keyword_query)):
                    keyword_query[i] = str(keyword_query[i])

            vector_result = []
            keyword_result = []

            # Retrieve documents with individual error handling
            try:
                # Input validation
                if not semantic_query or not isinstance(semantic_query, str):
                    raise ValueError("semantic_query must be a non-empty string")

                with timeout():
                    vector_result = __VectorRetriever(semantic_query)
            except ValueError as e:
                print(str(e))
            except QueryTimeoutError as e:
                print(f"Vector retriever timeout: {e}")
            except Exception as e:
                print(f"Vector retrieval failed: {e}")

            if keyword_query:
                try:
                    with timeout():
                        keyword_result = __KeywordRetriever(keyword_query)
                except QueryTimeoutError as e:
                    print(f"Keyword retriever timeout: {e}")
                except Exception as e:
                    print(f"Keyword retrieval failed: {e}")

            # Check if both retrievers failed
            if not vector_result and not keyword_result:
                print("Both retrieval methods failed")
                return [], {}

            total = vector_result + keyword_result
            overall_result = nodes_to_dicts(total)
            internal_result = {"ids": {node.node_id for node in total}}
            return overall_result, internal_result
        except Exception as e:
            print(f"Unexpected error: {e}")
            return [], {}

    return DocumentRetriever
