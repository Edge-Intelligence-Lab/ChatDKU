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
from llama_index.core.schema import BaseNode, MetadataMode
from llama_index.core.node_parser.text.token import TokenTextSplitter

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

    def forward(self, documents: list[BaseNode], query: str):
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


def get_reranker(top_n: int):
    return ColbertRerank(
        top_n=top_n,
        model="colbert-ir/colbertv2.0",
        tokenizer="colbert-ir/colbertv2.0",
        keep_retrieval_score=True,
    )


def get_url(path):
    # 检查路径中是否包含 'dku_website'
    if "dku_website" in path:
        # 提取 'dku_website/' 之后的内容
        start_index = path.find("dku_website/")
        sub_path = path[start_index + len("dku_website/") :]

        # 检查路径的结尾是否是 '.html' 并去掉 '/index.html'
        if sub_path.endswith("/index.html"):
            sub_path = sub_path[: -len("/index.html")]

        # 如果路径的结尾是 '.pdf'，不进行处理
        # 直接返回处理后的路径
        return sub_path
    return "no url"


def simplify_nodes(reranked_nodes):
    simple_dict = {}
    simple_dict["metadata"] = {}
    simple_dict["metadata"]["url"] = get_url(reranked_nodes.metadata["file_path"])
    simple_dict["metadata"]["last_modified_date"] = reranked_nodes.metadata[
        "last_modified_date"
    ]
    simple_dict["related_context"] = reranked_nodes.text
    return simple_dict


class VectorRetriever(dspy.Module):
    """Retrieve texts from the database that are semantically similar to the query."""

    def __init__(self, retriever_top_k: int = 10, reranker_top_n: int = 2):
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

        # TODO: We can try simplifying the nodes first, then summarize them.
        # Right now, only simplifying them still exceeds the context window.
        #
        # contexts_dict = []
        # for node in reranked_nodes:
        #     contexts_dict.append(simplify_nodes(node))
        # return dspy.Prediction(result=str(contexts_dict))

        return dspy.Prediction(
            result=self.summarizer(documents=reranked_nodes, query=query).summary
        )


class KeywordRetriever(dspy.Module):
    """Retrieve texts from the database that contain the same keywords in the query."""

    def __init__(self, retriever_top_k: int = 10, reranker_top_n: int = 2):
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

        # See notes above
        #
        # contexts_dict = []
        # for node in reranked_nodes:
        #     contexts_dict.append(simplify_nodes(node))
        # return dspy.Prediction(result=str(contexts_dict))

        return dspy.Prediction(
            result=self.summarizer(documents=reranked_nodes, query=query).summary
        )
