#!/usr/bin/env python3

from typing import Any
import traceback

from llama_index.core import Settings
from llama_index.core.base.llms.types import CompletionResponse

import functools
from dsp import LM
import dspy
from dspy.primitives.assertions import assert_transform_module, backtrack_handler

# FIXME: Stop using these patches whenever the issues were addressed by DSPy.
import dspy_patch

from llamaindex_tools import VectorRetriever, KeywordRetriever

from dspy_classes.plan import Planner
from dspy_classes.conversation_memory import ConversationMemory
from dspy_classes.tool_memory import ToolMemory
from dspy_classes.query_rewrite import QueryRewrite
from dspy_classes.prompt_settings import VERBOSE
from dspy_classes.synthesizer import Synthesizer
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


class Agent(dspy.Module):
    def __init__(self, max_iterations=5, streaming=False, get_intermediate=False):
        """
        Args:
            max_iterations: The maximum rounds of tool call/evaluation the agent
                could execute for a user message. This includes the first round
                of tool calls with the initial user message.
            streaming: If `True`, returns the LLM response as a streaming generator
                for `reponse` returned by synthesizer, else simply return the
                complete response as a string.
            get_itermediate: If `True`, `forward()` would return the synthesized
                result for each agent iteration as a generator.
        """

        super().__init__()
        self.max_iterations = max_iterations
        self.streaming = streaming
        self.get_intermediate = get_intermediate

        self.planner = assert_transform_module(
            Planner([VectorRetriever(), KeywordRetriever()]),
            functools.partial(backtrack_handler, max_backtracks=5),
        )
        self.conversation_memory = ConversationMemory()
        self.tool_memory = ToolMemory()
        self.synthesizer = Synthesizer()
        self.judge = assert_transform_module(
            Judge(), functools.partial(backtrack_handler, max_backtracks=5)
        )
        self.queryrewriter = QueryRewrite()

        self.prev_response = None

    def forward(self, current_user_message: str):
        # Reset tool memory for each user message
        # Need to make this an attribute so that DSPy can optimize it
        self.tool_memory.reset()

        # Add previous response to conversation memory
        if self.prev_response is not None:
            if self.streaming:
                # Note that this would essentially "invalidate" the previous response generator
                # as calling `get_full_response()` would exhaust the iterations.
                r = self.prev_response.get_full_response()
            else:
                r = self.prev_response
            self.conversation_memory(role="assistant", content=r)

        # FIXME: Pre-calling tools.
        # Currently, it calls ALL tools as the first iteration.
        # However, it has two issues:
        # 1. The API of the tools might differ in the future
        #    (having something other than `query` in parameters).
        # 2. It has issues with DSPy assertions.
        # 3. The zipping of the `name_to_model` and `tools` might be problematic.
        if VERBOSE:
            print("pre-calling tools")

        # Deal with DSPy assertions
        # Reference: https://github.com/stanfordnlp/dspy/blob/af5186cf07ab0b95d5a12690d5f7f90f202bc86e/dspy/predict/retry.py#L59
        with dspy.settings.lock:
            dspy.settings.backtrack_to = None

        import time

        for (name, model), tool in zip(
            self.planner.name_to_model.items(), self.planner.tools
        ):
            start_time = time.time()
            first_ite_result = tool(query=current_user_message).result
            if VERBOSE:
                print(f"result: {first_ite_result}")

            # 要计时的代码块
            end_time = time.time()

            elapsed_time = end_time - start_time
            print("---" * 100)
            print(f"Elapsed time: {elapsed_time} seconds")
            self.tool_memory(
                current_user_message=current_user_message,
                conversation_memory=self.conversation_memory,
                calls=[model(name=name, params={"query": current_user_message})],
                result=first_ite_result,
            )
            if VERBOSE:
                print(f"tool memory: {self.tool_memory.history}")

        synthesizer_args = dict(
            current_user_message=current_user_message,
            conversation_memory=self.conversation_memory,
            tool_memory=self.tool_memory,
            streaming=self.streaming,
        )

        # The subsequent rounds of tool calling
        for i in range(self.max_iterations - 1):
            # TODO: Could feed the intermediate response to judge
            # TODO: Could also try to make this async/threaded, so the output
            # with the user would be done simultaneous with the execution of the
            # next round. However, this would be contradictory to the previous
            # todo.
            if self.get_intermediate:
                yield self.synthesizer(**synthesizer_args)

            if VERBOSE:
                print(f"iteration: {i}")
            judgement = self.judge(
                current_user_message=current_user_message,
                conversation_memory=self.conversation_memory,
                tool_memory=self.tool_memory,
            ).judgement
            if VERBOSE:
                print(f"Judge: {judgement}")
            if judgement:
                break

            # TODO: This could be merged with `Planner` depends on how well the
            # LLM understood its task.
            rewritten_query = self.queryrewriter(
                current_user_message=current_user_message,
                conversation_memory=self.conversation_memory,
                tool_memory=self.tool_memory,
            ).rewritten_query
            if VERBOSE:
                print(f"rewritten query:{rewritten_query}")

            try:
                p = self.planner(
                    # Only using the rewritten query here but not for updating memory
                    # as the memory is not always updated for every iteration.
                    # Also, the memory should concern answering the overarching
                    # user question, while the planner can focus more on the current iteration.
                    current_user_message=rewritten_query,
                    conversation_memory=self.conversation_memory,
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
                current_user_message=current_user_message,
                conversation_memory=self.conversation_memory,
                calls=p.calls,
                result=result,
            )
            if VERBOSE:
                print(f"tool_memory.history: {self.tool_memory.history}")

        self.prev_response = self.synthesizer(**synthesizer_args).response
        self.conversation_memory(role="user", content=current_user_message)
        if self.get_intermediate:
            yield dspy.Prediction(response=self.prev_response)
        else:
            return dspy.Prediction(response=self.prev_response)


def main():
    setup()
    # TODO: Might try integration with DSPy instead of LlamaIndex for better traces
    # See: https://docs.arize.com/phoenix/tracing/integrations-tracing/dspy
    use_phoenix()

    llama_client = CustomClient()
    dspy.settings.configure(lm=llama_client)
    agent = Agent(max_iterations=5, streaming=True, get_intermediate=True)

    while True:
        try:
            print("*" * 10)
            current_user_message = input("Enter your query about DKU: ")
            responses_gen = agent(current_user_message=current_user_message)
            for i, r in enumerate(responses_gen):
                print("-" * 10)
                print(f"Round {i} response:")
                for r in r.response:
                    print(r, end="")
                print("-" * 10)
        except EOFError:
            break


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

    input()
