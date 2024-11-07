from typing import Annotated
from pydantic import Field

import dspy

from utils import truncate_tokens
from dspy_common import custom_cot_rationale
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

from redis import Redis
from redis.commands.search.query import Query

import os
import sys
import re
import string
from itertools import combinations

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../RAG"))
)
from config import config


def mydeepcopy(self, memo):
    return self


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

url_csv_path = "/datapool/download_info/download_info.csv"
df = pd.read_csv(url_csv_path)


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
                matching_row = df[df["file_path"] == result]
                if not matching_row.empty:
                    return matching_row.iloc[0]["url"]
        elif "new_bulletin" in path:
            match = re.search(r"new_bulletin/.*", path)
            if match:
                result = match.group(0)
                matching_row = df[df["file_path"] == result]
                if not matching_row.empty:
                    return matching_row.iloc[0]["url"]
        return "no url"
    except Exception as e:
        return f"no url, error: {str(e)}"


def get_str_of_simplified_nodes(nodes: list[NodeWithScore]):
    simplified_nodes = [
        TextNode(
            text=node.text,
            metadata={
                "url": get_url(node.metadata),
            },
        )
        for node in nodes
    ]

    return "\n\n".join(
        [node.get_content(MetadataMode.LLM) for node in simplified_nodes]
    )


class VectorRetriever(dspy.Module):
    """Retrieve texts from the database that are semantically similar to the query."""

    def __init__(self, retriever_top_k: int = 10, reranker_top_n: int = 5):
        db = chromadb.PersistentClient(path=config.chroma_db)
        chroma_collection = db.get_collection("dku_html_pdf")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        index = VectorStoreIndex.from_vector_store(vector_store)
        # self.retriever = TransformRetriever(
        #     retriever=index.as_retriever(similarity_top_k=retriever_top_k),
        #     query_transform=HyDEQueryTransform(include_original=True),
        # )
        self.retriever = index.as_retriever(similarity_top_k=retriever_top_k)

        self.reranker = get_reranker(reranker_top_n)

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
        retrieved_nodes = self.retriever.retrieve(
            # FIXME: bge-m3 has a max token limit of 8192. However, I do not know
            # what would happen if that is exceeded. Also, we should use it tokenizer
            # to get the accurate token count. This is just a temporary safety
            # measure for now.
            truncate_tokens(query, 7000)
        )
        reranked_nodes = self.reranker.postprocess_nodes(
            retrieved_nodes,
            # BERT token limit is 512, however, we should leave some space for special tokens
            query_str=truncate_tokens(query, 500, tokenizer=self.reranker._tokenizer),
        )
        return dspy.Prediction(
            result=get_str_of_simplified_nodes(reranked_nodes), internal_result={}
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

        try:
            nltk.data.find("tokenizers/punkt_tab")
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

        exclude = list(internal_memory.get("ids", set()))
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

        retriever_top_k = 5
        query_cmd = (
            Query(query_str).scorer("BM25").paging(0, retriever_top_k).with_scores()
        )
        results = self.client.ft("idx:test").search(query_cmd)
        print(results)
        try:
            nodes = [
                TextNode(text=r.text, metadata={"file_path": r.file_path})
                for r in results.docs
            ]
        except:
            nodes = [TextNode(text=r.text) for r in results.docs]

        ids = {r.id for r in results.docs}

        # retrieved_nodes = self.retriever.retrieve(query)
        # reranked_nodes = self.reranker.postprocess_nodes(
        #     retrieved_nodes,
        #     # BERT token limit is 512, however, we should leave some space for special tokens
        #     query_str=truncate_tokens(query, 500, tokenizer=self.reranker._tokenizer),
        # )
        # return dspy.Prediction(result=get_str_of_simplified_nodes(reranked_nodes))
        return dspy.Prediction(
            result=get_str_of_simplified_nodes(nodes), internal_result={"ids": ids}
        )

        # See notes about summarizer above
        # return dspy.Prediction(
        #     result=self.summarizer(documents=reranked_nodes, query=query).summary
        # )
