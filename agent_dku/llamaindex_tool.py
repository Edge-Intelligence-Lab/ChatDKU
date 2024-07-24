import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.indices.query.schema import QueryBundle
from llama_index.embeddings.text_embeddings_inference import (
    TextEmbeddingsInference,
)
from llama_index.core import Settings
from llama_index.postprocessor.colbert_rerank import ColbertRerank
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES

import os
import sys

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../RAG"))
)
from settings import Config

config = Config()

topk_from_retriever = 50
topn_from_rerank = 10

fusion_top_k = 50
bm25_top_k = 50


class LlamaindexTool:
    def __init__(self) -> None:
        Settings.embed_model = TextEmbeddingsInference(
            model_name=config.embedding,
            base_url=config.tei_url + "/" + config.embedding,
        )
        ### init llamaindex pipeline
        self.db = chromadb.PersistentClient(path=config.chroma_db)
        self.chroma_collection = self.db.get_or_create_collection("dku_html_pdf")
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.index = VectorStoreIndex.from_vector_store(self.vector_store)

        self.vector_retriever = VectorIndexRetriever(
            index=self.index,
            similarity_top_k=topk_from_retriever,
        )

        self.docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        self.bm25_retriever = BM25Retriever.from_defaults(
            docstore=self.docstore, similarity_top_k=bm25_top_k
        )

        # NOTE: I am not sure why, but when using this retriever you MUST supply an LLM,
        # otherwise errors will be reported at the synthesizer stage. While this might
        # be due to the need of using an LLM at the query generation stage, it still
        # won't work if you set num_queries=1.
        # NOTE: by Cody Jul 3, in the documentation I found that "num_queries=1" is to disable query generation
        self.fusion_retriever = QueryFusionRetriever(
            [self.vector_retriever, self.bm25_retriever],
            similarity_top_k=fusion_top_k,
            mode=FUSION_MODES.RECIPROCAL_RANK,
            use_async=True,
            verbose=True,
        )

        self.colbert_reranker = ColbertRerank(
            top_n=topn_from_rerank,
            model="colbert-ir/colbertv2.0",
            tokenizer="colbert-ir/colbertv2.0",
            keep_retrieval_score=True,
        )

        print("-" * 10 + "llamaindex_tool loaded" + "-" * 10)

    def query(self, query, retriever):
        ### get query bundle
        query_bundle = QueryBundle(query_str=query)
        ### select retriever
        if retriever == "fusion":
            retrieved_nodes = self.fusion_retriever._retrieve(query_bundle=query_bundle)
        elif retriever == "vector":
            retrieved_nodes = self.vector_retriever._retrieve(query_bundle=query_bundle)
        ### colbert rerank
        reranked_nodes = self.colbert_reranker._postprocess_nodes(
            nodes=retrieved_nodes, query_bundle=query_bundle
        )
        ### to compress the full contexts
        contexts = [node.text for node in reranked_nodes]
        ### return List[Node]
        return contexts, reranked_nodes


def main():
    query = "what do you know about DKU?"
    llamaindextool = LlamaindexTool()
    contexts, reranked_nodes = llamaindextool.query(query, "fusion")


if __name__ == "__main__":
    main()

