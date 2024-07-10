#!/usr/bin/env python3

from llama_index.core import VectorStoreIndex, get_response_synthesizer
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever, TransformRetriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.response_synthesizers import ResponseMode
from llama_index.postprocessor.colbert_rerank import ColbertRerank
from llama_index.core.query_pipeline import QueryPipeline, InputComponent

from settings import setup, use_phoenix
from config import Config

config = Config()


def get_pipeline(
    retriever_type: str = "vector",
    hyde: bool = True,
    vector_top_k: int = 10,
    bm25_top_k: int = 10,
    fusion_top_k: int = 10,
    fusion_mode: FUSION_MODES = FUSION_MODES.RECIPROCAL_RANK,
    num_queries: int = 3,
    synthesize_response: bool = True,
    response_mode: ResponseMode = ResponseMode.COMPACT,
    weight1: int = 0.6,
    weight2: int = 0.4,
    colbert_rerank: bool = True,
    rerank_top_n=10,
) -> QueryPipeline:
    """
    Constructs a RAG query pipeline.

    Args:
        retriever_type: Type of retriever to use.
            Supported values are `vector` and `fusion`.
        hyde: If `True`, first use HyDE (Hypothetical Document Embeddings)
            to transform the query string before retrieval.
        vector_top_k: Top k similar nodes to retrieve using vector retriever
            (they are the inputs to fusion retriever if used).
        bm25_top_k: Top k similar nodes to retrieve using BM25 retriever
            (they are the inputs to fusion retriever if used).
        fusion_top_k: Top k similar documents to retrieve using fusion retriever.
        fusion_mode: How fusion retriever should calculate the score of the nodes.
            See `llama_index.core.retrievers.fusion_retriever.FUSION_MODES` for details.
        num_queries: Number of queries to generate for fusion retriever.
        synthesize_response: Synthesize responses using LLM if `True`,
            or output a list of nodes retrived if `False`.
        response_mode: Mode of response synthesis, see
            `llama_index.core.response_synthesizers.ResponseMode` for details.
        weight1, weight2: Weights for the distribution based fusion.
        cohere_rerank: boolean value to decide to use cohere reranking
        cohere_top_k: Top k relevant nodes to retrieve with Cohere Rerank

    Returns:
        A query pipeline that could be executed by supplying input to its `run()` method.

    Raises:
        ValueError: If an unsupported or invalid parameters are provided.
    """

    db = chromadb.PersistentClient(path=config.chroma_db)
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)

    if hyde:
        # NOTE: `HyDEQueryTransform` would effectively not work if used as an
        # component of the query pipeline by itself, since it returns a `QueryBundle`
        # with custom embedding strings that would be dropped when passed down the
        # pipeline as only the `query_str` attribute would be sent to the next
        # component.
        vector_retriever = TransformRetriever(
            retriever=vector_retriever,
            query_transform=HyDEQueryTransform(include_original=True),
        )

    if retriever_type == "vector":
        retriever = vector_retriever

    elif retriever_type == "fusion":
        docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        bm25_retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=bm25_top_k
        )

        # NOTE: I am not sure why, but when using this retriever you MUST supply an LLM,
        # otherwise errors will be reported at the synthesizer stage. While this might
        # be due to the need of using an LLM at the query generation stage, it still
        # won't work if you set num_queries=1.
        # NOTE: by Cody Jul 3, in the documentation I found that "num_queries=1" is to disable query generation
        retriever = QueryFusionRetriever(
            [vector_retriever, bm25_retriever],
            similarity_top_k=fusion_top_k,
            mode=fusion_mode,
            num_queries=num_queries,
            use_async=True,
            verbose=True,
        )

    elif retriever_type == "distribution based fusion":
        docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        bm25_retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=bm25_top_k
        )

        retriever = QueryFusionRetriever(
            [vector_retriever, bm25_retriever],
            retriever_weights=[weight1, weight2],
            similarity_top_k=fusion_top_k,
            mode="dist_based_score",
            num_queries=num_queries,
            use_async=True,
            verbose=True,
        )

    else:
        raise ValueError(f"Unsupported retriever_type: {retriever_type}")

    pipeline = QueryPipeline(verbose=True)
    pipeline.add_modules(
        {
            "input": InputComponent(),
            "retriever": retriever,
        }
    )
    pipeline.add_link("input", "retriever")

    if colbert_rerank:
        colbert_reranker = ColbertRerank(
            top_n=rerank_top_n,
            model="colbert-ir/colbertv2.0",
            tokenizer="colbert-ir/colbertv2.0",
            keep_retrieval_score=True,
        )

        pipeline.add_modules(
            {
                "rerank": colbert_reranker,
            }
        )
        pipeline.add_link("input", "rerank", dest_key="query_str")
        pipeline.add_link("retriever", "rerank", dest_key="nodes")

    if synthesize_response:
        pipeline.add_modules(
            {
                "synthesizer": get_response_synthesizer(
                    response_mode=response_mode, streaming=True
                )
            }
        )
        pipeline.add_link("input", "synthesizer", dest_key="query_str")
        if colbert_rerank:
            pipeline.add_link("rerank", "synthesizer", dest_key="nodes")
        else:
            pipeline.add_link("retriever", "synthesizer", dest_key="nodes")

    return pipeline


def main():
    setup()
    use_phoenix()

    pipeline = get_pipeline()

    while True:
        try:
            print("*" * 32)
            query = input("Enter your query about DKU: ")
            # output = pipeline.run(input=query)
            # print("+" * 32)
            # print(output)
            output = pipeline.run(input=query)
            print("+" * 32)
            for text in output.response_gen:
                print(text, end="")
        except EOFError:
            break


if __name__ == "__main__":
    main()
