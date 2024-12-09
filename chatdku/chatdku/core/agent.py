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
import chatdku.core.dspy_patch

from chatdku.core.tools.llama_index import VectorRetriever, KeywordRetriever

from chatdku.core.dspy_classes.plan import Planner
from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.tool_memory import ToolMemory
from chatdku.core.dspy_classes.query_rewrite import QueryRewrite
from chatdku.core.dspy_classes.prompt_settings import VERBOSE
from chatdku.core.dspy_classes.synthesizer import Synthesizer
from chatdku.core.dspy_classes.judge import Judge

from contextlib import nullcontext
from openinference.instrumentation import safe_json_dumps
from opentelemetry.trace import Status, StatusCode, use_span
from openinference.semconv.trace import (
    SpanAttributes,
    OpenInferenceSpanKindValues,
    OpenInferenceMimeTypeValues,
)

from chatdku.config import config
from chatdku.setup import setup, use_phoenix


class CustomClient(LM):
    def __init__(self) -> None:
        self.provider = "default"
        self.history = []
        self.kwargs = {
            "temperature": Settings.llm.temperature,
            "max_tokens": config.context_window,
        }

    def basic_request(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        with (
            config.tracer.start_as_current_span("LLM")
            if hasattr(config, "tracer")
            else nullcontext()
        ) as span:
            span.set_attributes(
                {
                    SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.LLM.value,
                    SpanAttributes.INPUT_VALUE: prompt,
                    SpanAttributes.LLM_MODEL_NAME: config.llm,
                    SpanAttributes.LLM_INVOCATION_PARAMETERS: safe_json_dumps(kwargs),
                }
            )

            response = Settings.llm.complete(prompt, **kwargs)
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, response.text)
            self.history.append(
                {
                    "prompt": prompt,
                    "response": response,
                    "kwargs": kwargs,
                }
            )

            span.set_status(Status(StatusCode.OK))
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
    def __init__(
        self,
        max_iterations: int = 5,
        streaming: bool = False,
        get_intermediate: bool = False,
        rewrite_query: bool = False,
    ):
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
        self.rewrite_query = rewrite_query

        self.planner = assert_transform_module(
            Planner([VectorRetriever(), KeywordRetriever()]),
            functools.partial(backtrack_handler, max_backtracks=5),
        )
        self.conversation_memory = ConversationMemory()
        self.tool_memory = ToolMemory()

        # Store information not accessible to the LLM.
        # Currently, only `ids` is stored, which tracks the documents already retrieved,
        # so they can be excluded in the subsequent retrievals.
        # NOTE: `VectorRetriever` and `KeywordRetriever` currently uses two different id formats,
        # but mixing them appears to not cause any issues.
        self.internal_memory = {}
        self.synthesizer = Synthesizer()
        self.judge = assert_transform_module(
            Judge(), functools.partial(backtrack_handler, max_backtracks=5)
        )
        self.queryrewriter = QueryRewrite()

        self.prev_response = None

    def reset(self):
        self.prev_response = None
        self.conversation_memory = ConversationMemory()

    def _forward_gen(self, current_user_message: str, question_id: str):
        # I cannot use the span as a context manager that wraps around the entire function
        # due to that this is a generator.
        # More about the issue regarding the use of `with` in generators:
        # https://stackoverflow.com/questions/41881731/is-it-safe-to-combine-with-and-yield-in-python
        if hasattr(config, "tracer"):
            span = config.tracer.start_span("Agent")
            span.set_attributes(
                {
                    SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.AGENT.value,
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(
                        dict(
                            current_user_message=current_user_message,
                            question_id=question_id,
                        )
                    ),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

        with use_span(span) if hasattr(config, "tracer") else nullcontext():
            # Putting this in `self.__init__()` might not work due to that you might
            # want DSPy to change prompt dynamically.

            # These limits are for compressing both tool and conversation memory.
            # Technically this only ensures that these memories would fit sufficiently
            # in `Planner` and not e.g. `QueryRewrite`, but this should be sufficient for now.
            # TODO: We could notify user when their input is too long.
            limits = self.planner.get_token_limits()

            # Reset tool memory for each user message
            # Need to make this an attribute so that DSPy can optimize it
            self.tool_memory.reset()

            # Clear internal memory for each user message
            self.internal_memory.clear()

            # Add previous response to conversation memory
            if self.prev_response is not None:
                if self.streaming:
                    # Note that this would essentially "invalidate" the previous response generator
                    # as calling `get_full_response()` would exhaust the iterations.
                    r = self.prev_response.get_full_response()
                else:
                    r = self.prev_response
                self.conversation_memory(
                    role="assistant",
                    content=r,
                    max_history_size=limits["conversation_history"],
                )

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

            for (name, model), tool in zip(
                self.planner.name_to_model.items(), self.planner.tools
            ):
                r = tool(
                    query=current_user_message, internal_memory=self.internal_memory
                )
                first_ite_result, internal_result = r.result, r.internal_result
                if "ids" in internal_result:
                    self.internal_memory["ids"] = (
                        self.internal_memory.get("ids", set()) | internal_result["ids"]
                    )
                # if VERBOSE:
                #     print(f"result: {first_ite_result}")

                self.tool_memory(
                    current_user_message=current_user_message,
                    conversation_memory=self.conversation_memory,
                    calls=[model(name=name, params={"query": current_user_message})],
                    result=first_ite_result,
                    max_history_size=limits["tool_history"],
                )
                # if VERBOSE:
                #     print(f"tool memory: {self.tool_memory.history_str()}")

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
                with use_span(span) if hasattr(config, "tracer") else nullcontext():
                    result = self.synthesizer(**synthesizer_args)
                yield result

            with use_span(span) if hasattr(config, "tracer") else nullcontext():
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

                if self.rewrite_query:
                    # TODO: This could be merged with `Planner` depends on how well the
                    # LLM understood its task.
                    query = self.queryrewriter(
                        current_user_message=current_user_message,
                        conversation_memory=self.conversation_memory,
                        tool_memory=self.tool_memory,
                    ).rewritten_query
                    if VERBOSE:
                        print(f"rewritten query:{query}")
                else:
                    query = current_user_message

                try:
                    p = self.planner(
                        # Only using the rewritten query here but not for updating memory
                        # as the memory is not always updated for every iteration.
                        # Also, the memory should concern answering the overarching
                        # user question, while the planner can focus more on the current iteration.
                        current_user_message=query,
                        conversation_memory=self.conversation_memory,
                        tool_memory=self.tool_memory,
                        max_calls=self.max_iterations - i,
                    )
                    if VERBOSE:
                        print(f"Planner:{p}")
                except dspy.DSPyAssertionError:
                    if VERBOSE:
                        print("max assertion retries hit")
                    break

                if VERBOSE:
                    print(f"calls: {p.calls}")

                r = p.tool(
                    **p.calls[0].params.model_dump(),
                    internal_memory=self.internal_memory,
                )
                result, internal_result = r.result, r.internal_result
                if "ids" in internal_result:
                    self.internal_memory["ids"] = (
                        self.internal_memory.get("ids", set()) | internal_result["ids"]
                    )

                if VERBOSE:
                    print(f"result: {result}")
                self.tool_memory(
                    current_user_message=current_user_message,
                    conversation_memory=self.conversation_memory,
                    calls=p.calls,
                    result=result,
                    max_history_size=limits["tool_history"],
                )
                # if VERBOSE:
                #     print(f"tool_memory.history: {self.tool_memory.history_str()}")

        with use_span(span) if hasattr(config, "tracer") else nullcontext():
            self.prev_response = self.synthesizer(
                **synthesizer_args, final=True
            ).response
            self.conversation_memory(
                role="user",
                content=current_user_message,
                max_history_size=limits["conversation_history"],
            )

        if not self.streaming:
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, self.prev_response)
            span.set_status(Status(StatusCode.OK))
            span.end()
        yield dspy.Prediction(response=self.prev_response)

    def forward(self, current_user_message: str, question_id: str = ""):
        gen = self._forward_gen(current_user_message, question_id)
        if self.get_intermediate:
            return gen
        else:
            for i in gen:
                return i


def main():
    setup()
    # TODO: Might try integration with DSPy instead of LlamaIndex for better traces
    # See: https://docs.arize.com/phoenix/tracing/integrations-tracing/dspy
    use_phoenix()

    llama_client = CustomClient()
    dspy.settings.configure(lm=llama_client)
    import time

    agent = Agent(max_iterations=1, streaming=True, get_intermediate=False)

    while True:
        try:
            print("*" * 10)
            current_user_message = input("Enter your query about DKU: ")
            start_time = time.time()
            responses_gen = agent(current_user_message=current_user_message)
            first_token = True
            print("Response:")
            for r in responses_gen.response:
                if first_token:
                    end_time = time.time()
                    print(f"first token时间:{end_time-start_time}")
                    first_token = False
                print(r, end="")
            print()

            # for i, r in enumerate(responses_gen):
            #     print("-" * 10)
            #     print(f"Round {i} response:")
            #     for r in r.response:
            #         if first_token:
            #             end_time = time.time()
            #             print(f"first token时间:{end_time-start_time}")
            #             first_token = False
            #         print(r, end="")
            #     print()
            #     print("-" * 10)
        except EOFError:
            break


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

    input()
