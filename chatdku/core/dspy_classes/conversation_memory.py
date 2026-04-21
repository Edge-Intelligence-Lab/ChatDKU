import json

import dspy
from litellm.exceptions import ContextWindowExceededError
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode

from chatdku.core.utils import span_ctx_start


MAX_HISTORY_ENTRIES = 6
TRUNCATE_BATCH_SIZE = 2


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
        self.history: list[dict] = []
        self.summary: str = ""

    def history_str(self) -> str:
        return "\n".join(json.dumps(entry) for entry in self.history)

    def forward(self, role: str, content: str):
        with span_ctx_start(
            "Conversation Memory", OpenInferenceSpanKindValues.CHAIN
        ) as span:
            new_entry = {role: content}
            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(new_entry),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            self.history.append(new_entry)

            if len(self.history) > MAX_HISTORY_ENTRIES:
                self._compress_oldest_with_retry(TRUNCATE_BATCH_SIZE)

            span.set_attributes(
                {
                    SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                        dict(history=self.history, summary=self.summary)
                    ),
                    SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )
            span.set_status(Status(StatusCode.OK))

    def register_history(self, role: str, content: str):
        self.history.append({role: content})

    def _compress_oldest_with_retry(self, batch_size: int):
        """Summarize the oldest `batch_size` entries into the running summary.

        On context window overflow, shrinks the batch one entry at a time and
        retries (up to 3 attempts), mirroring the pattern in Executor.
        """
        to_discard = self.history[:batch_size]
        remaining = self.history[batch_size:]

        for _ in range(3):
            try:
                self.summary = self._summarize(to_discard, self.summary)
                self.history = remaining
                return
            except ContextWindowExceededError:
                if len(to_discard) <= 1:
                    raise ValueError(
                        "The conversation history exceeded the context window even with a single entry."
                    )
                self.summary = self._summarize([to_discard[0]], self.summary)
                to_discard = to_discard[1:]

        raise ValueError(
            "The context window was exceeded even after 3 attempts to truncate the conversation history."
        )

    def _summarize(self, entries: list[dict], previous_summary: str) -> str:
        return self.compressor(
            history_to_discard="\n".join(json.dumps(e) for e in entries),
            previous_summary=previous_summary,
        ).current_summary
