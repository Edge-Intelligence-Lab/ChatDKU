#!/usr/bin/env python3

from argparse import ArgumentParser
from llama_index.core import VectorStoreIndex, get_response_synthesizer
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.tools import RetrieverTool
from llama_index.core.selectors import LLMSingleSelector

# from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import RouterRetriever

# from llama_index.core.retrievers import QueryFusionRetriever, TransformRetriever
# from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.response_synthesizers import ResponseMode
from llama_index.core.query_pipeline import QueryPipeline, InputComponent

import os
import phoenix as px
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from settings import Config, get_parser, setup


def get_pipeline(
    # retriever_type: str = "fusion",
    # hyde: bool = True,
    # vector_top_k: int = 5,
    # bm25_top_k: int = 5,
    # fusion_top_k: int = 5,
    # fusion_mode: FUSION_MODES = FUSION_MODES.RECIPROCAL_RANK,
    # num_queries: int = 3,
    top_k: int = 5,
    synthesize_response: bool = True,
    response_mode: ResponseMode = ResponseMode.COMPACT,
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

    Returns:
        A query pipeline that could be executed by supplying input to its `run()` method.

    Raises:
        ValueError: If an unsupported or invalid parameters are provided.
    """

    db = chromadb.PersistentClient(path=Config.vector_store_path)
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    vector_retriever = index.as_retriever(similarity_top_k=top_k)

    # if hyde:
    #     # NOTE: `HyDEQueryTransform` would effectively not work if used as an
    #     # component of the query pipeline by itself, since it returns a `QueryBundle`
    #     # with custom embedding strings that would be dropped when passed down the
    #     # pipeline as only the `query_str` attribute would be sent to the next
    #     # component.
    #     vector_retriever = TransformRetriever(
    #         retriever=vector_retriever,
    #         query_transform=HyDEQueryTransform(include_original=True),
    #     )

    # if retriever_type == "vector":
    #     retriever = vector_retriever

    # elif retriever_type == "fusion":
    docstore = SimpleDocumentStore.from_persist_path(Config.docstore_path)
    bm25_retriever = BM25Retriever.from_defaults(
        docstore=docstore, similarity_top_k=top_k
    )

    # NOTE: I am not sure why, but when using this retriever you MUST supply an LLM,
    # otherwise errors will be reported at the synthesizer stage. While this might
    # be due to the need of using an LLM at the query generation stage, it still
    # won't work if you set num_queries=1.
    # retriever = QueryFusionRetriever(
    #     [vector_retriever, bm25_retriever],
    #     similarity_top_k=fusion_top_k,
    #     mode=fusion_mode,
    #     num_queries=num_queries,
    #     use_async=True,
    #     verbose=True,
    # )

    # else:
    #     raise ValueError(f"Unsupported retriever_type: {retriever_type}")

    vector_tool = RetrieverTool.from_defaults(
        retriever=vector_retriever,
        description="Retrieve texts semantically similar to the query.",
    )
    keyword_tool = RetrieverTool.from_defaults(
        retriever=bm25_retriever,
        description="Retrieve texts that contain the same keywords given in the query.",
    )
    retriever = RouterRetriever(
        selector=LLMSingleSelector.from_defaults(),
        retriever_tools=[
            vector_tool,
            keyword_tool,
        ],
    )

    pipeline = QueryPipeline(verbose=True)
    pipeline.add_modules(
        {
            "input": InputComponent(),
            "retriever": retriever,
        }
    )
    pipeline.add_link("input", "retriever")

    if synthesize_response:
        pipeline.add_modules(
            {
                "synthesizer": get_response_synthesizer(
                    response_mode=response_mode, streaming=True
                )
            }
        )
        pipeline.add_link("input", "synthesizer", dest_key="query_str")
        pipeline.add_link("retriever", "synthesizer", dest_key="nodes")

    return pipeline


def main():
    parser = ArgumentParser(parents=[get_parser()])
    args = parser.parse_args()
    setup(args)

    # NOTE: I cannot find how to disable gRPC for Phoenix, so I would just
    # pass in port 0 to make it easier to avoid port collision.
    os.environ["PHOENIX_GRPC_PORT"] = "0"
    px.launch_app()
    phoenix_port = os.environ.get("PHOENIX_PORT", 6006)
    endpoint = f"http://127.0.0.1:{phoenix_port}/v1/traces"
    tracer_provider = trace_sdk.TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint)))
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)

    pipeline = get_pipeline(
        # retriever_type="fusion",
        #  hyde=True,
        #  vector_top_k=5,
        #  bm25_top_k=5,
        #  fusion_top_k=5,
        #  fusion_mode=FUSION_MODES.RECIPROCAL_RANK,
        #  num_queries=3,
        synthesize_response=True,
        response_mode=ResponseMode.COMPACT,
    )

    while True:
        try:
            print("*" * 32)
            query = input("> ")
            output = pipeline.run(input=query)
            print("+" * 32)
            print(output)
        except EOFError:
            break


if __name__ == "__main__":
    main()
