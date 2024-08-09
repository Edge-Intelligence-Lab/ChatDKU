from typing import Annotated
from pydantic import Field

import dspy

from utils import truncate_tokens
from dspy_common import custom_cot_rationale

import chromadb
import llama_index
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.postprocessor.colbert_rerank import ColbertRerank
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.schema import TextNode, NodeWithScore, MetadataMode
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


def get_str_of_simplified_nodes(nodes: list[NodeWithScore]):
    simplified_nodes = [
        TextNode(
            text=node.text,
            metadata={
                "url": get_url(node.metadata["file_path"]),
                "last_modified_date": node.metadata["last_modified_date"],
            },
        )
        for node in nodes
    ]
    return "\n\n".join(
        [node.get_content(MetadataMode.LLM) for node in simplified_nodes]
    )


class VectorRetriever(dspy.Module):
    """Retrieve texts from the database that are semantically similar to the query."""

    def __init__(self, retriever_top_k: int = 10, reranker_top_n: int = 2):
        db = chromadb.PersistentClient(path=config.chroma_db)
        chroma_collection = db.get_collection("dku_html_pdf")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        index = VectorStoreIndex.from_vector_store(vector_store)
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
        return dspy.Prediction(result=get_str_of_simplified_nodes(reranked_nodes))

        # See notes about summarizer above
        # return dspy.Prediction(
        #     result=self.summarizer(documents=reranked_nodes, query=query).summary
        # )


class KeywordRetriever(dspy.Module):
    """Retrieve texts from the database that contain the same keywords in the query."""

    def __init__(self, retriever_top_k: int = 10, reranker_top_n: int = 2):
        docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        self.retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=retriever_top_k
        )

        self.reranker = get_reranker(reranker_top_n)

        # self.summarizer = DocumentSummarizer()

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
            retrieved_nodes,
            # BERT token limit is 512, however, we should leave some space for special tokens
            query_str=truncate_tokens(query, 500, tokenizer=self.reranker._tokenizer),
        )
        return dspy.Prediction(result=get_str_of_simplified_nodes(reranked_nodes))

        # See notes about summarizer above
        # return dspy.Prediction(
        #     result=self.summarizer(documents=reranked_nodes, query=query).summary
        # )
