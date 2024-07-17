#!/usr/bin/env python3

import json
from typing import Any
from llama_index.core import VectorStoreIndex, get_response_synthesizer
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever

from llama_index.core import Settings
from llama_index.core.base.llms.types import CompletionResponse

import functools
from dsp import LM
import dspy
import dsp
from dspy.teleprompt import BootstrapFewShot
from dspy.evaluate import Evaluate
from dspy.primitives.assertions import assert_transform_module, backtrack_handler
from dspy import Predict
from dspy.signatures.signature import ensure_signature, signature_to_template


from settings import setup, use_phoenix
from config import Config

config = Config()

import llama_index


def mydeepcopy(self, memo):
    return self


# FIXME: Ugly hack for the issue that DSPy's use of `deepcopy()` cannot copy
# certain attributes (probably due to the being Pydantic `PrivateAttr()`?)
llama_index.vector_stores.chroma.ChromaVectorStore.__deepcopy__ = mydeepcopy


class CustomClient(LM):
    def __init__(self) -> None:
        self.provider = "default"
        self.history = []
        self.kwargs = {
            "temperature": Settings.llm.temperature,
            "max_tokens": Settings.llm.context_window,
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


def get_template(predict_module: Predict) -> str:
    """Get formatted template from predict module."""
    """Adapted from https://github.com/stanfordnlp/dspy/blob/55510eec1b83fa77f368e191a363c150df8c5b02/dspy/predict/llamaindex.py#L22-L36"""
    # Extract the three privileged keyword arguments.
    signature = ensure_signature(predict_module.signature)
    # Switch to legacy format for dsp.generate
    template = signature_to_template(signature)

    if hasattr(predict_module, "demos"):
        demos = predict_module.demos
    else:
        demos = []
    # All of the other kwargs are presumed to fit a prefix of the signature.
    # That is, they are input variables for the bottom most generation, so
    # we place them inside the input - x - together with the demos.
    x = dsp.Example(demos=demos)
    return template(x)


class RetrieverSelector(dspy.Signature):
    """Choose the best retriever type and generate a query for querying the database for texts that could answer the question."""

    question = dspy.InputField(desc="The question to be answered.")
    retriever_type = dspy.OutputField(
        desc="The best type of retriever to use for the given question.\n"
        '"vector": Retrieves texts that are semantically similar to the query.\n'
        '"keyword": Retrieves texts that contain the same keywords used in the query.'
    )
    query = dspy.OutputField(
        desc="The query string to use for querying relevant texts.\n"
        'If retriever is "vector", write a passage that might be semantically similar to the real answer to the question.\n'
        'If retriever is "keyword", generate some keywords that might appear in the answer to the question.'
    )


class Rag(dspy.Module):
    def __init__(self, vector_top_k, keyword_top_k):
        super().__init__()
        self.retriever_selector = dspy.ChainOfThought(RetrieverSelector)

        db = chromadb.PersistentClient(path=config.chroma_db)
        chroma_collection = db.get_or_create_collection("dku_html_pdf")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        index = VectorStoreIndex.from_vector_store(vector_store)
        self.vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)

        docstore = SimpleDocumentStore.from_persist_path(config.docstore_path)
        self.keyword_retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=keyword_top_k
        )

        self.response_synthesizer = get_response_synthesizer()

    def forward(self, question):
        s = self.retriever_selector(question=question)
        dspy.Suggest(
            s.retriever_type in ["vector", "keyword"],
            'The retriever type should be either "vector" or "keyword".',
        )
        if s.retriever_type == "vector":
            retriever = self.vector_retriever
        elif s.retriever_type == "keyword":
            retriever = self.keyword_retriever
        else:
            print(
                f"Unsupported retriever_type: {s.retriever_type}, fall back to vector retriever"
            )
            retriever = self.vector_retriever

        nodes = retriever.retrieve(s.query)
        response = self.response_synthesizer.synthesize(question, nodes=nodes)
        return dspy.Prediction(answer=str(response))


class Judge(dspy.Signature):
    """Judge if the current answer is equivalent to the ground truth answer to the question."""

    question: str = dspy.InputField(desc="The question to be answered.")
    ground_truth: str = dspy.InputField(desc="The ground truth answer to the question.")
    answer: str = dspy.InputField(desc="The current answer to be judged.")
    judgement: bool = dspy.OutputField(
        desc="Whether the current answer is equivalent to the ground truth."
    )


def main():
    setup()
    use_phoenix()

    llama_client = CustomClient()
    dspy.settings.configure(lm=llama_client)

    file_path = "../datasets/before_RAG_dataset.json"
    with open(file_path, "r", encoding="utf-8") as file:
        json_data = json.load(file)
    dataset = [
        dspy.Example(question=d["question"], answer=d["ground_truth"]).with_inputs(
            "question"
        )
        for d in json_data
    ]

    trainset, devset = dataset[50:55], dataset[60:65]

    judge = dspy.TypedPredictor(Judge)

    def metric(example, pred, trace=None):
        prediction = judge(
            question=example.question, ground_truth=example.answer, answer=pred.answer
        )
        return prediction.judgement

    config = dict(max_bootstrapped_demos=3, max_labeled_demos=0, max_errors=1)
    teleprompter = BootstrapFewShot(metric=metric, **config)

    # try:

    rag_with_assertions = assert_transform_module(
        Rag(vector_top_k=5, keyword_top_k=5),
        functools.partial(backtrack_handler, max_backtracks=3),
    )
    rag = teleprompter.compile(rag_with_assertions, trainset=trainset)
    # except:
    #     input()

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
