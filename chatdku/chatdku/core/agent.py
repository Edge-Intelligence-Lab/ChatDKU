#!/usr/bin/env python3
import traceback

import dspy
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry.trace import Status, StatusCode, use_span

from chatdku.config import config
from chatdku.core.dspy_classes.memory import ConversationMemory, PermanentMemory
from chatdku.core.dspy_classes.plan import Planner, format_trajectory
from chatdku.core.dspy_classes.synthesizer import Synthesizer
from chatdku.core.tools.llama_index import KeywordRetrieverOuter, VectorRetrieverOuter
from chatdku.core.tools.memory_tool import MemoryTools

from chatdku.core.tools.llama_index_pg import DocRetrieverOuter
from chatdku.core.tools.syllabi_tool.query_curriculum_db import QueryCurriculumOuter
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

        self.planner = Planner(tools, max_iterations)

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
            # Putting this in `self.__init__()` might not work due to that you might
            # want DSPy to change prompt dynamically.

            # These limits are for compressing both tool and conversation memory.
            # Technically this only ensures that these memories would fit sufficiently
            # in `Planner` and not e.g. `QueryRewrite`, but this should be sufficient for now.
            # TODO: We could notify user when their input is too long.
            limits = self.planner.get_token_limits(
                current_user_message=current_user_message,
                conversation_history=self.conversation_memory.history_str(),
                trajectory=format_trajectory({}),
            )

            # Clear internal memory for each user message
            self.internal_memory.clear()

            # Add previous response to conversation memory
            if self.prev_response is not None:
                if self.streaming:
                    # Note that this would essentially "invalidate" the previous response generator
                    # as calling `get_full_response()` would exhaust the iterations.
                    prev_response = self.prev_response.get_full_response()
                else:
                    prev_response = self.prev_response
                self.conversation_memory(
                    role="assistant",
                    content=prev_response,
                    max_history_size=limits["conversation_history"],
                )

            plan = self.planner(
                current_user_message=current_user_message,
                conversation_history=self.conversation_memory.history_str(),
                conversation_summary=self.conversation_memory.summary,
            )
            synthesizer_args = dict(
                current_user_message=current_user_message,
                conversation_memory=self.conversation_memory,
                trajectory=plan.trajectory,
                trajectory_summary=plan.summary,
                streaming=self.streaming,
            )

            self.prev_response = self.synthesizer(**synthesizer_args).response
            self.conversation_memory(
                role="user",
                content=current_user_message,
                max_history_size=limits["conversation_history"],
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


def main():
    setup()
    use_phoenix()

    lm = dspy.LM(
        model="openai/" + config.backup_llm,
        api_base=config.backup_llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=config.output_window,
        temperature=config.llm_temperature,
    )
    dspy.configure(lm=lm)
    # To disable cache:

    # dspy.configure_cache(
    # enable_disk_cache=False,
    # enable_memory_cache=False
    # )

    import time

    role = "student"
    access_type = "student"  # hard code it for now, need parameter pass from user role
    user_id = "Chat_DKU"
    search_mode = 0
    memory = MemoryTools(user_id)
    tools = [
        DocRetrieverOuter(
            retriever_top_k=25,
            use_reranker=True,
            reranker_top_n=5,
            access_type=access_type,
            role=role,
            user_id=user_id,
            search_mode=search_mode,
            files=[],
        ),
        QueryCurriculumOuter(),
        memory.search_memories,
        memory.get_all_memories,
    ]

    agent = Agent(
        max_iterations=3,
        streaming=True,
        get_intermediate=False,
        tools=tools,
    )

    permanent_memory = PermanentMemory(user_id=user_id)
    conversations = []
    while True:
        try:
            print("*" * 10)
            current_user_message = input("Enter your query about DKU: ")
            start_time = time.time()
            responses_gen = agent(
                current_user_message=current_user_message,
            ).response
            first_token = True
            print("Response:")
            for r in responses_gen:
                if first_token:
                    end_time = time.time()
                    print(f"first token时间:{end_time - start_time}")
                    first_token = False
                print(r, end="")
            print()

            recent_conversation = [
                {"role": "user", "content": current_user_message},
                {"role": "assistant", "content": responses_gen.get_full_response()},
            ]
            permanent_memory(
                session_conversation=conversations,
                most_recent_conversation=recent_conversation,
            )
            conversations.append(recent_conversation)

        except EOFError:
            break


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())

    input()
