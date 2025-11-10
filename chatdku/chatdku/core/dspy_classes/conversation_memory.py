from pydantic import BaseModel, ConfigDict
from typing import Optional

from chatdku.core.utils import (
    strs_fit_max_tokens_reverse,
    token_limit_ratio_to_count,
    truncate_tokens_all,
)
from chatdku.core.dspy_common import get_template
import dspy

from contextlib import nullcontext
from openinference.instrumentation import safe_json_dumps
from opentelemetry.trace import Status, StatusCode
from openinference.semconv.trace import (
    SpanAttributes,
    OpenInferenceSpanKindValues,
    OpenInferenceMimeTypeValues,
)

from chatdku.config import config


class ConversationMemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    content: str


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

    def history_str(self, l: int = 0, r: Optional[int] = None):
        if r is None:
            r = len(self.history)

        return "\n".join(
            [
                i.model_dump_json(indent=4)
                for i in self.history[l:r]
                if not isinstance(i, dict)
            ]
        )

    def get_token_limits(self, **kwargs) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.compressor, **kwargs))
        )

    def forward(self, role: str, content: str, max_history_size: int = 1000):
        with (
            config.tracer.start_as_current_span("Conversation Memory")
            if hasattr(config, "tracer")
            else nullcontext()
        ) as span:
            span.set_attribute(
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                OpenInferenceSpanKindValues.CHAIN.value,
            )
            new_entry = ConversationMemoryEntry(role=role, content=content)
            self.history.append(new_entry)
            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(new_entry.model_dump()),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

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
