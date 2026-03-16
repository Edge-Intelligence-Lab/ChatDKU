"""Memory related module. Currently has Temporary Memory and Permanent Memory."""

from typing import Optional

import dspy
from litellm.exceptions import ContextWindowExceededError
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel, ConfigDict

from chatdku.core.dspy_classes.plan import _fmt_exc, create_react_signature
from chatdku.core.dspy_common import get_template
from chatdku.core.tools.memory_tool import MemoryTools
from chatdku.core.utils import (
    span_ctx_start,
    strs_fit_max_tokens_reverse,
    token_limit_ratio_to_count,
    truncate_tokens_all,
)


class ConversationMemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    content: str


class PermanentMemorySignature(dspy.Signature):
    """You are a Memory Management Agent. In each episode, you are given available tools.
    And you can see your past trajectory so far. Your goal is to use one or more of the
    supplied tools to store OR update OR delete any useful facts about the user from the
    most_recent_conversation.
    To do this, you will produce next_thought, next_tool_name, and next_tool_args in each turn,
    and also when finishing the task.
    After each tool call, you receive a resulting observation, which gets appended to your trajectory.
    When writing next_thought, you may reason about the current situation and plan for future steps.
    When selecting the next_tool_name and its next_tool_args, the tool must be one of the provided tools.

    For your convenience, all the user_memories are given to you. Based on the latest conversation,
    you may update any memory that needs updating and may also delete any memory that is no longer relevant.

    If the most_recent_conversation does not contain any useful information,
    you should immediately use "finish" tool.
    """

    session_conversation: dict[str, str] = dspy.InputField()
    user_memories: list[str] = dspy.InputField()
    most_recent_conversation: dict[str, str] = dspy.InputField()


class PermanentMemory(dspy.Module):
    def __init__(self, user_id):
        super().__init__()
        memory = MemoryTools(user_id)
        tools = [
            memory.store_memory,
            memory.delete_memory,
            memory.update_memory,
        ]
        react_signature, tools = create_react_signature(PermanentMemorySignature, tools)
        self.tools = tools
        self.user_memories = memory.get_all_memories()
        self.planner = dspy.Predict(react_signature)

    def forward(
        self,
        session_conversation: list[dict[str, str]],
        most_recent_conversation: list[dict[str, str]],
    ):
        planner_inputs = dict(
            user_memories=self.user_memories,
            most_recent_conversation=most_recent_conversation,
        )
        trajectory = {}
        with span_ctx_start(
            "Permanent Memory",
            OpenInferenceSpanKindValues.AGENT,
        ) as span:
            span.set_attribute("agent.name", "PermanentMemoryAgent")
            span.set_attribute("input.value", safe_json_dumps(planner_inputs))

            for idx in range(5):
                planner_inputs["trajectory"] = trajectory
                try:
                    plan = self._call_with_potential_conversation_truncation(
                        self.planner,
                        session_conversation=session_conversation,
                        **planner_inputs,
                    )
                except ValueError as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    break

                trajectory[f"thought_{idx}"] = plan.next_thought
                trajectory[f"tool_name_{idx}"] = plan.next_tool_name
                trajectory[f"tool_args_{idx}"] = plan.next_tool_args

                try:
                    trajectory[f"observation_{idx}"] = self.tools[plan.next_tool_name](
                        **plan.next_tool_args
                    )
                except Exception as err:
                    trajectory[f"observation_{idx}"] = (
                        f"Execution error in {plan.next_tool_name}: {_fmt_exc(err)}"
                    )
                if plan.next_tool_name == "finish":
                    break
            span.set_attribute("output.value", safe_json_dumps(trajectory))
        return dspy.Prediction()

    def _call_with_potential_conversation_truncation(
        self, module, session_conversation: dict, **input_args
    ):
        for _ in range(3):
            try:
                return module(
                    **input_args,
                    session_conversation=session_conversation,
                )
            except ContextWindowExceededError:
                # Conversation exceeded the context window
                # truncating the oldest tool call information.
                session_conversation = self.truncate_conversation(session_conversation)
        raise ValueError(
            "The context window was exceeded even after 3 attempts to truncate the trajectory."
        )

    def truncate_conversation(self, conversation: dict) -> dict:
        """Truncates the earliest conversation so that it fits in the context window."""
        keys = list(conversation.keys())

        for key in keys[:2]:
            conversation.pop(key)

        return conversation


class CompressConversationMemorySignature(dspy.Signature):
    """
    You have a Conversation History storing all the conversations between user
    and you, the assistant.
    Your Conversation History has become too long, so the oldest entries have to be discarded.
    You keep a Summary of the discarded conversation history.
    Given the History To Discard and Previous Summary, update the Summary.
    Use Markdown in Summary.
    """

    history_to_discard: str = dspy.InputField(
        desc=(
            "The conversation messages that would be removed from your Conversation History in JSON Lines format. "
            "Each line specifies the role and content of the message."
        )
    )

    previous_summary: str = dspy.InputField(
        desc="Previous summary of the discarded Conversation History. Might be empty.",
        format=lambda x: x,
    )

    current_summary: str = dspy.OutputField(
        desc="Your updated summary.",
    )


class ConversationMemory(dspy.Module):
    def __init__(self):
        super().__init__()
        self.compressor = dspy.Predict(CompressConversationMemorySignature)
        self.history: list[ConversationMemoryEntry] = []
        self.summary: str = ""
        self.token_ratios: dict[str, float] = {
            "history_to_discard": 2 / 4,
            "previous_summary": 1 / 4,
        }

    def history_str(self, left: int = 0, right: Optional[int] = None):
        if right is None:
            right = len(self.history)

        return "\n".join(
            [
                i.model_dump_json(indent=4)
                for i in self.history[left:right]
                if not isinstance(i, dict)
            ]
        )

    def get_token_limits(self, **kwargs) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.compressor, **kwargs))
        )

    def forward(self, role: str, content: str, max_history_size: int = 1000):
        with span_ctx_start(
            "Conversation Memory", OpenInferenceSpanKindValues.CHAIN
        ) as span:
            new_entry = ConversationMemoryEntry(role=role, content=content)
            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(new_entry.model_dump()),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            self.history.append(new_entry)

            min_index = strs_fit_max_tokens_reverse(
                [i.model_dump_json() for i in self.history if not isinstance(i, dict)],
                "\n",
                max_history_size,
            )
            if min_index > 0:
                compressor_inputs = dict(
                    history_to_discard=self.history_str(0, min_index),
                    previous_summary=self.summary,
                )
                compressor_inputs = truncate_tokens_all(
                    compressor_inputs, self.get_token_limits(**compressor_inputs)
                )
                self.summary = self.compressor(**compressor_inputs).current_summary
                self.history = self.history[min_index:]

            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                        dict(
                            history=[
                                i.model_dump()
                                for i in self.history
                                if not isinstance(i, dict)
                            ],
                            summary=self.summary,
                        )
                    ),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))

    def register_history(self, role: str, content: str):
        new_entry = ConversationMemoryEntry(role=role, content=content)
        self.history.append(new_entry)
