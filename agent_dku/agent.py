#!/usr/bin/env python3

from typing import Any, Callable, Literal
from pydantic import BaseModel, ConfigDict, Field, create_model, ValidationError
from pydantic.fields import FieldInfo
from inspect import signature, Signature
import re
import traceback

from llama_index.core import Settings
from llama_index.core.base.llms.types import CompletionResponse

import functools
from dsp import LM
import dspy
import dsp
from dspy.primitives.assertions import assert_transform_module, backtrack_handler
from dspy import Predict
from dspy.signatures.signature import ensure_signature, signature_to_template

# FIXME: Stop using these patches whenever the issues were addressed by DSPy.
import dspy_patch

from dspy_common import custom_cot_rationale
from llamaindex_tools import VectorRetriever, KeywordRetriever

from dspy_classes.plan import Planner
from dspy_classes.query_rewrite import QueryRewrite
from dspy_classes.prompt_settings import VERBOSE
from dspy_classes.contexts import Contexts
from dspy_classes.synthesizer import SynthesizerSignature
from dspy_classes.tool_memory import ToolMemory
from dspy_classes.judge import Judge

import os
import sys

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../RAG"))
)
from settings import Config, setup, use_phoenix

config = Config()




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


# When executing tasks like summarizing, the LLM is supposed to ONLY generate the
# summaries themselves. However, the LLM sometimes says things like
# `here is a summary of the given text` before the summary. This prompt used to
# explicitly discourage this kind of output.
#
# Also note that I have tried other things like `do not begin your answer with
# "here are the generated queries"` to discourage such messages at the beginning of
# the generated queries. Nevertheless, this prompt seems to be the most effective.
#
# FIXME: Use a more suitable system prompt



class Agent(dspy.Module):
    def __init__(self, max_iterations=5):
        super().__init__()
        self.max_iterations = max_iterations

        # FIXME: This duplication is currently required.
        # See notes below regarding pre-calling tools for more.
        self.tools = [VectorRetriever(), KeywordRetriever()]
        self.planner = assert_transform_module(
            Planner(tools=[VectorRetriever(), KeywordRetriever()]),
            functools.partial(backtrack_handler, max_backtracks=5),
        )
        self.tool_memory = ToolMemory()
        self.synthesizer = dspy.ChainOfThought(
            SynthesizerSignature, rationale_type=custom_cot_rationale
        )
        self.judge = assert_transform_module(
            Judge(), functools.partial(backtrack_handler, max_backtracks=5)
        )
        self.queryrewriter = QueryRewrite()
        self.contexts = Contexts()

    def forward(self, current_user_message: str):
        # Need to make this an attribute so that DSPy can optimize it
        # self.tool_memory.reset()
        self.contexts.reset()

        # FIXME: Pre-calling tools.
        # Currently, it calls ALL tools as the first iteration.xw
        # However, it has two issues:
        # 1. The API of the tools might differ in the future
        #    (having something other than `query` in parameters).
        # 2. It cannot directly call the tools in `self.planner` as they were
        #    transformed by DSPy assertions, which would cause issues when
        #    calling them before calling planner. Therefore, a duplicate set
        #    of tools is required.
        # 3. The zipping of the `name_to_model` and `tools` might be problematic.
        if VERBOSE:
            print("pre-calling tools")

        import time

        for (name, model), tool in zip(self.planner.name_to_model.items(), self.tools):
            start_time = time.time()
            first_ite_result = str(tool(query=current_user_message))
            if VERBOSE:
                print(f"result: {first_ite_result}")

                    # 要计时的代码块
            end_time = time.time()

            elapsed_time = end_time - start_time
            print("---"*100)
            print(f"Elapsed time: {elapsed_time} seconds")
            # self.contexts(
            #     current_user_message=current_user_message,
            #     result=first_ite_result,
            # )
            self.contexts(
                current_user_message=current_user_message,
                result=first_ite_result,
            )
            if VERBOSE:
                print(f"contexts memory: {self.contexts.memory}")



        for i in range(self.max_iterations - 1):
            if VERBOSE:
                print(f"iteration: {i}")
            # NOTE: Should judge only when there were tool calls before.
            # Currently, the first iteration is actually calling all the tools.
            judgement = self.judge(
                question=current_user_message,
                known_information=self.contexts.memory,
            )
            if VERBOSE:
                print(f"Judge: {judgement}")
            if judgement:
                break

            rewrited_query = self.queryrewriter(
                    question=current_user_message,
                    known_information=self.tool_memory.memory,
            )       
            if VERBOSE:
                print(f"rewrited query:{rewrited_query}")

            try:
                p = self.planner(
                    current_user_message=rewrited_query,
                    tool_memory=self.tool_memory,
                    max_calls=self.max_iterations - i,
                )
            except dspy.DSPyAssertionError:
                if VERBOSE:
                    print("max assertion retries hit")
                break

            if VERBOSE:
                print(f"calls: {p.calls}")
            result = p.tool(**p.calls[0].params.model_dump()).result
            if VERBOSE:
                print(f"result: {result}")
            self.tool_memory(
                current_user_message=rewrited_query,
                schema=p.schema,
                calls=p.calls,
                result=result,
            )
            if VERBOSE:
                print(f"tool_memory.memory: {self.tool_memory.memory}")

        ### summarize result here
       

        return dspy.Prediction(
            response=self.synthesizer(
                current_user_message=current_user_message,
                tool_memory=self.contexts.memory,
            ).response
        )


def main():
    setup()
    # use_phoenix()

    llama_client = CustomClient()
    dspy.settings.configure(lm=llama_client)

    current_user_message = "What do you know about DKU, Please answer in more detail"
    agent = Agent(max_iterations=5)
    response = agent(current_user_message=current_user_message).response
    print(f"response: {response}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

    input()
