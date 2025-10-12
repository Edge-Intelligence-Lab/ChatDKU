#!/usr/bin/env python3
import dspy

from chatdku.core.tools.llama_index import VectorRetrieverOuter, KeywordRetrieverOuter

# from chatdku.core.tools.syllabi_tool.query_curriculum_db import QueryCurriculumDB

# from chatdku.core.dspy_classes.plan import Planner
from chatdku.core.dspy_classes.plan import Planner
from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.tool_memory import ToolMemory
from chatdku.core.dspy_classes.query_rewrite import QueryRewrite
from chatdku.core.dspy_classes.prompt_settings import VERBOSE
from chatdku.core.dspy_classes.synthesizer import Synthesizer
from chatdku.core.dspy_classes.judge import Judge

from contextlib import nullcontext
from openinference.instrumentation import safe_json_dumps
import traceback
from opentelemetry.trace import Status, StatusCode, use_span
from openinference.semconv.trace import (
    SpanAttributes,
    OpenInferenceSpanKindValues,
    OpenInferenceMimeTypeValues,
)

from chatdku.config import config
from chatdku.setup import setup, use_phoenix
from chatdku.core.utils import load_conversation


class Agent(dspy.Module):
    def __init__(
        self,
        max_iterations: int = 5,
        streaming: bool = False,
        get_intermediate: bool = False,
        rewrite_query: bool = True,
        previous_conversation: list = None,
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
            previous_conversation: List of User-Assistant conversation retrieved from the database.
        """

        super().__init__()
        self.max_iterations = max_iterations
        self.streaming = streaming
        self.get_intermediate = get_intermediate
        self.rewrite_query = rewrite_query

        self.planner = Planner()

        self.conversation_memory = ConversationMemory()

        try:
            if previous_conversation:
                past_conversations = load_conversation(previous_conversation)

                for conversation in past_conversations:
                    user, bot = conversation[0], conversation[1]
                    self.conversation_memory.register_history(role="user", content=user)
                    self.conversation_memory.register_history(
                        role="assistant", content=bot
                    )
        except Exception as e:
            print(f"error encountered in loading conversation: {e}")

        self.tool_memory = ToolMemory()

        # Store information not accessible to the LLM.
        # Currently, only `ids` is stored, which tracks the documents already retrieved,
        # so they can be excluded in the subsequent retrievals.
        # NOTE: `VectorRetriever` and `KeywordRetriever` currently uses two different id formats,
        # but mixing them appears to not cause any issues.
        self.internal_memory = {}
        self.synthesizer = Synthesizer()
        self.judge = Judge()
        self.queryrewriter = QueryRewrite()

        self.prev_response = None

    def reset(self):
        self.prev_response = None
        self.conversation_memory = ConversationMemory()

    def _forward_gen(
        self,
        current_user_message: str,
        question_id: str,
        user_id: str,
        search_mode: int,
        files: list,
    ):
        # Define the tools here. Wrap them in dspy.Tool()
        # Currently only supports functions.
        self.tools = {
            "VectorRetriever": dspy.Tool(
                VectorRetrieverOuter(
                    user_id=user_id,
                    search_mode=search_mode,
                    files=files,
                    internal_memory=self.internal_memory,
                )
            ),
            "KeywordRetriever": dspy.Tool(
                KeywordRetrieverOuter(
                    user_id=user_id,
                    search_mode=search_mode,
                    files=files,
                    internal_memory=self.internal_memory,
                )
            ),
        }

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
            limits = self.planner.get_token_limits(
                current_user_message=current_user_message,
                tool_history=self.tool_memory.history_str(),
                tool_summary=self.tool_memory.summary,
                previous_tool_plan=str(self.tool_memory.plan),
                conversation_history=self.conversation_memory.history_str(),
                conversation_summary=self.conversation_memory.summary,
                tools=str(list(self.tools.values())),
                max_calls=str(2),
            )

            # Reset tool memory for each user message
            # Need to make this an attribute so that DSPy can optimize it
            self.tool_memory.reset()

            # Clear internal memory for each user message
            self.internal_memory.clear()

            for tool in self.tools.values():
                result, internal_result = tool(query=current_user_message)

                if "ids" in internal_result:
                    self.internal_memory["ids"] = (
                        self.internal_memory.get("ids", set()) | internal_result["ids"]
                    )

                if VERBOSE:
                    print(f"result: {result}")

                self.tool_memory(
                    current_user_message=current_user_message,
                    conversation_memory=self.conversation_memory,
                    call=tool,
                    result=result,
                    max_history_size=limits["tool_history"],
                )

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

            synthesizer_args = dict(
                current_user_message=current_user_message,
                conversation_memory=self.conversation_memory,
                tool_memory=self.tool_memory,
                streaming=self.streaming,
            )

        query = current_user_message
        # The subsequent rounds of tool calling
        for i in range(self.max_iterations):
            if VERBOSE:
                print(f"iteration: {i}")
            with use_span(span) if hasattr(config, "tracer") else nullcontext():
                judgement = self.judge(
                    current_user_message=current_user_message,
                    conversation_memory=self.conversation_memory,
                    tool_memory=self.tool_memory,
                ).judgement

                if VERBOSE:
                    print(f"Judge: {judgement}")
                if judgement:
                    break

                try:
                    planner = self.planner(
                        # Only using the rewritten query here but not for updating memory
                        # as the memory is not always updated for every iteration.
                        # Also, the memory should concern answering the overarching
                        # user question, while the planner can focus more on the current iteration.
                        current_user_message=query,
                        tools=self.tools,
                        conversation_memory=self.conversation_memory,
                        tool_memory=self.tool_memory,
                        # FIXME: Change this number when we add more tools
                        max_calls=2,
                    )
                    if VERBOSE:
                        print(f"Planner:{planner}")
                except Exception as e:
                    if VERBOSE:
                        print(e)
                    break

                if VERBOSE:
                    print(f"calls: {planner.tool_plan}")

                for tool in planner.tool_plan.tool_calls:
                    result, internal_result = self.tools[tool.name](**tool.args)

                    if "ids" in internal_result:
                        self.internal_memory["ids"] = (
                            self.internal_memory.get("ids", set())
                            | internal_result["ids"]
                        )

                    if VERBOSE:
                        print(f"result: {result}")

                    self.tool_memory(
                        current_user_message=current_user_message,
                        conversation_memory=self.conversation_memory,
                        call=tool,
                        result=result,
                        max_history_size=limits["tool_history"],
                    )

                if VERBOSE:
                    print(f"tool_memory.history: {self.tool_memory.history_str()}")

                if self.rewrite_query:
                    query = self.queryrewriter(
                        current_user_message=current_user_message,
                        conversation_memory=self.conversation_memory,
                        tool_memory=self.tool_memory,
                    ).rewritten_query
                    if VERBOSE:
                        print(f"rewritten query:{query}")

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

    def forward(
        self,
        current_user_message: str,
        question_id: str = "",
        user_id: str = "Chat_DKU",
        search_mode: int = 0,
        files: list = None,
        lm: dspy.LM = None,
    ):
        """
        current_user_message: user query
        user_id: If set anything other than Chat_DKU, means the net_id of the user
        search_mode: 0 for searching  the default corpus | 1 for searching the user
            corpus | 2 for searching both
        docs: Names of documents searching. Required for search_mode 1 or 2.
        """
        dspy.settings.configure(lm=lm)

        if files is None:
            files = []

        if not (0 <= search_mode <= 2):
            raise ValueError(
                f"Invalid search_mode: {search_mode}. Must be between 0 and 2."
            )

        if search_mode != 0 and not files:
            raise ValueError("`docs` must be provided when search_mode is 1 or 2.")

        gen = self._forward_gen(
            current_user_message,
            question_id,
            user_id=user_id,
            search_mode=search_mode,
            files=files,
        )

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

    lm = dspy.LM(
        model="openai/" + config.backup_llm,
        api_base=config.backup_llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=config.context_window,
        temperature=config.llm_temperature,
        launch_kwargs={
            "TopP": 0.95,
            "enable_thinking": False,
        },
    )
    # To disable cache:

    # dspy.configure_cache(
    # enable_disk_cache=False,
    # enable_memory_cache=False
    # )

    import time

    agent = Agent(
        max_iterations=2,
        streaming=True,
        get_intermediate=False,
    )

    user_id = input("Input your user id (Chat_DKU for default): ") or "Chat_DKU"
    search_mode_input = input("Search mode (0 for default): ")
    search_mode = int(search_mode_input) if search_mode_input else 0

    while True:
        try:
            print("*" * 10)
            current_user_message = input("Enter your query about DKU: ")
            start_time = time.time()
            responses_gen = agent(
                current_user_message=current_user_message,
                user_id=user_id,
                search_mode=search_mode,
                files=[],
                lm=lm,
            )
            first_token = True
            print("Response:")
            for r in responses_gen.response:
                if first_token:
                    end_time = time.time()
                    print(f"first token时间:{end_time - start_time}")
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
