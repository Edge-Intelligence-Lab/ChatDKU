#!/usr/bin/env python3
"""
WIP: Script for DSPy to compile (auto-optimize) our Agent module.
It does not work yet, only serving as template for future work.
"""

import json
from typing import Any, Callable, Literal
from pydantic import BaseModel, ConfigDict, Field, create_model, ValidationError
from pydantic.fields import FieldInfo
from inspect import signature, Signature
import re

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

from agent import CustomClient, Agent, Judge

import os
import sys

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../RAG"))
)
from settings import Config, setup, use_phoenix

config = Config()


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

    trainset, devset = dataset[50:51], dataset[60:61]

    judge = assert_transform_module(
        Judge(),
        functools.partial(backtrack_handler, max_backtracks=3),
    )

    def metric(example, pred, trace=None):
        prediction = judge(
            question=example.question, ground_truth=example.answer, answer=pred.answer
        )
        return prediction.judgement

    config = dict(max_bootstrapped_demos=1, max_labeled_demos=0, max_errors=1)
    teleprompter = BootstrapFewShot(metric=metric, **config)

    # try:

    rag = assert_transform_module(
        Rag(vector_top_k=5, keyword_top_k=5),
        functools.partial(backtrack_handler, max_backtracks=3),
    )
    rag = teleprompter.compile(rag, trainset=trainset)
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


if __name__ == "__main__":
    main()
