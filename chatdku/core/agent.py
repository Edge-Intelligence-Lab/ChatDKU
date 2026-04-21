#!/usr/bin/env python3
import argparse
import os
import sys
import traceback
import pyfiglet

# Must be set before `import dspy` — prevents litellm from fetching the remote
# model pricing database at startup (cuts ~40s off cold-start time).
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import dspy
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry.trace import Status, StatusCode, use_span

from chatdku.config import config
from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.executor import Executor
from chatdku.core.dspy_classes.plan import Planner
from chatdku.core.dspy_classes.synthesizer import Synthesizer
from chatdku.core.tools.course_recommender import CourseRecommender
from chatdku.core.tools.course_schedule import CourseScheduleLookup
from chatdku.core.tools.get_prerequisites import PrerequisiteLookup
from chatdku.core.tools.llama_index_tools import (
    KeywordRetrieverOuter,
    VectorRetrieverOuter,
)
from chatdku.core.tools.major_requirements import MajorRequirementsLookup
from chatdku.core.tools.syllabi.syllabi_tool import SyllabusLookupOuter
from chatdku.core.utils import load_conversation, span_start
from chatdku.setup import setup, use_phoenix

# When `--dev` is passed to the script, enable additional debug prints in this module.
DEBUG_DEV = False


class Agent(dspy.Module):
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

    def __init__(
        self,
        max_iterations: int = 5,
        streaming: bool = False,
        get_intermediate: bool = False,
        rewrite_query: bool = True,
        previous_conversation: list = [],
        tools: list = [],
    ):
        super().__init__()
        self.streaming = streaming
        self.get_intermediate = get_intermediate
        self.rewrite_query = rewrite_query
        # Store information not accessible to the LLM.
        # Currently, only `ids` is stored, which tracks the documents already retrieved,
        # so they can be excluded in the subsequent retrievals.
        # NOTE: `VectorRetriever` and `KeywordRetriever` currently uses two different id formats,
        # but mixing them appears to not cause any issues.
        # Edit (Temuulen): nahhh it is causing issues.
        self.internal_memory = {}

        self.planner = Planner(tools)
        self.executor = Executor(tools, max_iterations)

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

        self.synthesizer = Synthesizer()

        self.prev_response = None

    def reset(self):
        self.prev_response = None
        self.conversation_memory = ConversationMemory()

    def _forward_gen(
        self,
        current_user_message: str,
        question_id: str,
    ):
        span = span_start(
            span_name="Agent",
            span_kind=OpenInferenceSpanKindValues.CHAIN,
            current_user_message=current_user_message,
            question_id=question_id,
        )

        with use_span(span):
            # Clear internal memory for each user message
            self.internal_memory.clear()

            # Add previous response to conversation memory
            if self.prev_response is not None:
                if isinstance(self.prev_response, str):
                    prev_response = self.prev_response
                else:
                    # NOTE: that this would essentially "invalidate" the previous response generator
                    # as calling `get_full_response()` would exhaust the iterations.
                    prev_response = self.prev_response.get_full_response()
                self.conversation_memory(
                    role="assistant",
                    content=prev_response,
                )

            plan_result = self.planner(
                current_user_message=current_user_message,
                conversation_memory=self.conversation_memory,
            )

            if plan_result.action_type == "send_message":
                # Short-circuit: planner responded directly (follow-up question,
                # conversational reply, or request for more info).
                self.prev_response = plan_result.action
            else:
                # Planner produced a plan — hand it to the executor.
                execution = self.executor(
                    plan=plan_result.action,
                    current_user_message=current_user_message,
                    conversation_memory=self.conversation_memory,
                )
                synthesizer_args = dict(
                    current_user_message=current_user_message,
                    conversation_memory=self.conversation_memory,
                    relevant_context=execution.relevant_context,
                    trajectory_summary=execution.summary,
                    streaming=self.streaming,
                )

                self.prev_response = self.synthesizer(**synthesizer_args).response

            self.conversation_memory(
                role="user",
                content=current_user_message,
            )

        if not self.streaming:
            if span is not None:
                span.set_attribute(SpanAttributes.OUTPUT_VALUE, self.prev_response)
                span.set_status(Status(StatusCode.OK))
                span.end()
        yield dspy.Prediction(response=self.prev_response)

    def forward(
        self,
        current_user_message: str,
        question_id: str = "",
    ):
        """
        current_user_message: user query
        """

        gen = self._forward_gen(
            current_user_message,
            question_id,
        )

        if self.get_intermediate:
            return gen
        else:
            for i in gen:
                return i


def build_agent(streaming: bool = True, max_iterations: int = 5) -> "Agent":
    """Configure DSPy and return a ready-to-use Agent instance."""
    setup()
    use_phoenix()

    lm = dspy.LM(
        model="openai/" + config.llm,
        api_base=config.llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=config.output_window,
        top_p=config.top_p,
        min_p=config.min_p,
        presence_penalty=config.presence_penalty,
        repetition_penalty=config.repetition_penalty,
        temperature=config.llm_temperature,
        extra_body={
            "top_k": config.top_k,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        enable_thinking=False,
    )
    dspy.configure(lm=lm)

    # To disable cache:
    # dspy.configure_cache(
    # enable_disk_cache=False,
    # enable_memory_cache=False
    # )

    user_id = "Chat_DKU"
    search_mode = 0
    tools = [
        KeywordRetrieverOuter(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id=user_id,
            search_mode=search_mode,
            files=[],
        ),
        VectorRetrieverOuter(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id=user_id,
            search_mode=search_mode,
            files=[],
        ),
        SyllabusLookupOuter(),
        MajorRequirementsLookup,
        PrerequisiteLookup,
        CourseRecommender,
        CourseScheduleLookup,
    ]

    return Agent(
        max_iterations=max_iterations,
        streaming=streaming,
        get_intermediate=False,
        tools=tools,
    )


def run_query(query: str, agent: "Agent | None" = None) -> str:
    """Run a single query and return the full response as a string.

    Suitable for programmatic use from Python:
        from chatdku.core.agent import run_query
        print(run_query("What are the CS major requirements?"))
    """
    if agent is None:
        agent = build_agent(streaming=False)
    result = agent(current_user_message=query)
    response = result.response
    if isinstance(response, str):
        return response
    # Streaming generator — collect.
    return "".join(response)


def main():
    parser = argparse.ArgumentParser(description="ChatDKU agent.")
    parser.add_argument(
        "query",
        nargs="*",
        help="Query to run once and exit. If omitted, starts interactive mode.",
    )
    args = parser.parse_args()

    if args.query:
        query = " ".join(args.query)
        print(run_query(query))
        return

    _main_interactive()


def _main_interactive():
    import time

    agent = build_agent(streaming=True)

    pyfiglet.figlet_format("ChatDKU", font="slant")

    while True:
        try:
            print("*" * 10)
            current_user_message = input("Enter your query about DKU: ")
            start_time = time.time()
            responses_gen = agent(
                current_user_message=current_user_message,
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

        except EOFError:
            break


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
        if sys.stdin.isatty():
            input()
