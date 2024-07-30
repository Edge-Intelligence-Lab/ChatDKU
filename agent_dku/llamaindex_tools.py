from typing import Annotated
from pydantic import Field

import dspy

from dspy_common import custom_cot_rationale

import chromadb
import llama_index
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.postprocessor.colbert_rerank import ColbertRerank
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever

import os
import sys

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../RAG"))
)
from settings import Config

config = Config()


def mydeepcopy(self, memo):
    return self


# FIXME: Ugly hack for the issue that DSPy's use of `deepcopy()` cannot copy
# certain attributes (probably due to the being Pydantic `PrivateAttr()`?)
llama_index.vector_stores.chroma.ChromaVectorStore.__deepcopy__ = mydeepcopy


class DocumentSummarizerSignature(dspy.Signature):
    """Update the summary with information in the documents that are relevant to the query."""

    previous_summary = dspy.InputField(
        desc="The previously generated summary of relevant information. May be empty."
    )
    documents = dspy.InputField(
        desc="The documents to extract relevant information from."
    )
    query = dspy.InputField(desc="The query that the summary should answer.")
    current_summary = dspy.OutputField(
        desc="The combined summary of relevant information in Previous Summary and Documents."
    )


class DocumentSummarizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarizer = dspy.ChainOfThought(
            DocumentSummarizerSignature, rationale_type=custom_cot_rationale
        )

    def forward(self, documents, query):
        summary = ""
        for doc in documents:
            summary = self.summarizer(
                previous_summary=summary, documents=doc, query=query
            ).current_summary
        return dspy.Prediction(summary=summary)


def get_reranker(top_n: int):
    return ColbertRerank(
        top_n=top_n,
        model="colbert-ir/colbertv2.0",
        tokenizer="colbert-ir/colbertv2.0",
        keep_retrieval_score=True,
    )


class VectorRetriever(dspy.Module):
    """Retrieve texts from the database that are semantically similar to the query."""

    def __init__(self, retriever_top_k: int = 10, reranker_top_n: int = 5):
        db = chromadb.PersistentClient(path=config.chroma_db)
        chroma_collection = db.get_collection("dku_html_pdf")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        index = VectorStoreIndex.from_vector_store(vector_store)
        self.retriever = index.as_retriever(similarity_top_k=retriever_top_k)

        self.reranker = get_reranker(reranker_top_n)

        self.summarizer = DocumentSummarizer()

    def forward(
        self,
        query: Annotated[
            str,
            Field(
                description="Texts that might be semantically similar to the real answer to the question."
            ),
        ],
    ):
        retrieved_nodes = self.retriever.retrieve(query)
        reranked_nodes = self.reranker.postprocess_nodes(
            retrieved_nodes, query_str=query
        )
        texts = [node.get_content() for node in reranked_nodes]
        return dspy.Prediction(
            result=self.summarizer(documents=texts, query=query).summary
        )


class KeywordRetriever(dspy.Module):
    """Retrieve texts from the database that contain the same keywords in the query."""

    def __init__(self, retriever_top_k: int = 10, reranker_top_n: int = 5):
        docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        self.retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=retriever_top_k
        )

        self.reranker = get_reranker(reranker_top_n)

        self.summarizer = DocumentSummarizer()

    def forward(
        self,
        query: Annotated[
            str,
            Field(
                description="Keywords that might appear in the answer to the question."
            ),
        ],
    ):
        retrieved_nodes = self.retriever.retrieve(query)
        reranked_nodes = self.reranker.postprocess_nodes(
            retrieved_nodes, query_str=query
        )
        texts = [node.get_content() for node in reranked_nodes]
        return dspy.Prediction(
            result=self.summarizer(documents=texts, query=query).summary
        )
