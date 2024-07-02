#!/usr/bin/env python3

import json
from argparse import ArgumentParser
from typing import Any
from enum import Enum
from llama_index.core import VectorStoreIndex, get_response_synthesizer
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.query_engine import RetrieverQueryEngine

from llama_index.core import Settings
from llama_index.core.base.llms.types import CompletionResponse

import os
import phoenix as px
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from dsp import LM
import dspy
from dspy.teleprompt import BootstrapFewShot
from dspy.evaluate import Evaluate

from settings import Config, get_parser, setup


class LlamaClient(LM):
    def __init__(self) -> None:
        self.provider = "default"
        self.history = []
        self.kwargs = {
            "temperature": Settings.llm.temperature,
            "max_tokens": Settings.llm.max_new_tokens,
        }

    def basic_request(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        response = Settings.llm.complete(prompt, **kwargs)
        self.history.append(
            {
                "prompt": prompt,
                "response": response,
                "kwargs": kwargs,
            }
        )
        return response

    def inspect_history(self, n: int = 1, skip: int = 0) -> str:
        last_prompt = None
        printed = []
        n = n + skip

        for x in reversed(self.history[-100:]):
            prompt = x["prompt"]
            if prompt != last_prompt:
                printed.append((prompt, x["response"].text))
            last_prompt = prompt
            if len(printed) >= n:
                break

        printing_value = ""
        for idx, (prompt, text) in enumerate(reversed(printed)):
            # skip the first `skip` prompts
            if (n - idx - 1) < skip:
                continue
            printing_value += "\n\n\n"
            printing_value += prompt
            printing_value += self.print_green(text, end="")
            printing_value += "\n\n\n"

        print(printing_value)
        return printing_value

    def __call__(
        self,
        prompt: str,
        only_completed: bool = True,
        return_sorted: bool = False,
        **kwargs: Any,
    ) -> list[str]:
        return [self.request(prompt, **kwargs).text]


class RetrieverType(Enum):
    VECTOR = "vector"
    KEYWORD = "keyword"


class RetrieverSelector(dspy.Signature):
    """
    Choose the best retriever for querying database for relevant texts that could answer the given question.
    "vector": retrieves texts that are semantically similar to the question.
    "keyword": retrieves texts that contain the same keywords used in the question.
    """

    question: str = dspy.InputField(
        desc="The question to be answered, which would also be passed to the retriever you chose."
    )
    retriever_type: RetrieverType = dspy.OutputField(
        desc="The best type of retriever to use for the given question."
    )


class Rag(dspy.Module):
    def __init__(self, vector_top_k: int = 5, keyword_top_k: int = 5):
        super().__init__()
        db = chromadb.PersistentClient(path=Config.vector_store_path)
        chroma_collection = db.get_or_create_collection("dku_html_pdf")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        index = VectorStoreIndex.from_vector_store(vector_store)
        self.vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)

        docstore = SimpleDocumentStore.from_persist_path(Config.docstore_path)
        self.keyword_retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=keyword_top_k
        )

        self.retriever_selector = dspy.TypedChainOfThought(RetrieverSelector)

    def forward(self, question):
        # retriever_type = self.retriever_selector(question=question).retriever_type
        # if retriever_type == RetrieverType.VECTOR:
        #     retriever = self.vector_retriever
        # elif retriever_type == RetrieverType.KEYWORD:
        #     retriever = self.keyword_retriever
        # else:
        #     print(
        #         f"Unsupported retriever_type: {retriever_type}, fall back to vector retriever"
        #     )
        #     retriever = self.vector_retriever

        retriever = self.vector_retriever
        query_engine = RetrieverQueryEngine(
            retriever=retriever, response_synthesizer=get_response_synthesizer()
        )
        return dspy.Prediction(answer=str(query_engine.query(question)))


class Judge(dspy.Signature):
    """Judge if the current answer is equivalent to the ground truth answer to the question."""

    question: str = dspy.InputField(desc="The question to be answered.")
    ground_truth: str = dspy.InputField(desc="The ground truth answer to the question.")
    answer: str = dspy.InputField(desc="The current answer to be judged.")
    judgement: bool = dspy.OutputField(
        desc="Whether the current answer is equivalent to the ground truth."
    )


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

    llama_client = LlamaClient()
    dspy.settings.configure(lm=llama_client)

    file_path = "../RAG_evaluate/data_for_rag/before_RAG_dataset.json"
    with open(file_path, "r", encoding="utf-8") as file:
        json_data = json.load(file)
    dataset = [
        dspy.Example(question=d["question"], answer=d["ground_truth"]).with_inputs(
            "question"
        )
        for d in json_data
    ]

    trainset, devset = dataset[50:55], dataset[50:55]

    judge = dspy.TypedPredictor(Judge)

    def metric(example, pred, trace=None):
        prediction = judge(
            question=example.question, ground_truth=example.answer, answer=pred.answer
        )
        return prediction.judgement

    config = dict(max_bootstrapped_demos=4, max_labeled_demos=4)
    teleprompter = BootstrapFewShot(metric=metric, **config)
    try:
        rag = teleprompter.compile(Rag(), trainset=trainset)
    except:
        input()
    rag.save("compiled_rag.json")

    # Set up the evaluator, which can be used multiple times.
    evaluate = Evaluate(
        devset=devset,
        metric=metric,
        num_threads=1,  # Multi-threading won't work for our local model
        display_progress=True,
        display_table=True,
    )

    # Evaluate our `optimized_cot` program.
    evaluate(rag)

    print(llama_client.inspect_history(n=1))

    input()

    # while True:
    #     try:
    #         print("*" * 32)
    #         query = input("> ")
    #         output = pipeline.run(input=query)
    #         print("+" * 32)
    #         print(output)
    #     except EOFError:
    #         break


if __name__ == "__main__":
    main()
