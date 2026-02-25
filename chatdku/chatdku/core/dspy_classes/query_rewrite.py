from contextlib import nullcontext

import dspy
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode

from chatdku.config import config
from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.prompt_settings import (
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    CURRENT_USER_MESSAGE_FIELD,
    ROLE_PROMPT,
    TOOL_HISTORY_FIELD,
    TOOL_SUMMARY_FIELD,
)
from chatdku.core.dspy_classes.tool_memory import ToolMemory
from chatdku.core.dspy_common import get_template
from chatdku.core.utils import token_limit_ratio_to_count, truncate_tokens_all


class QueryRewriteSignature(dspy.Signature):
    """
    You goal is to rewrite the current user's message in a way that fixes errors,
    adds relevant contextual information from the conversation_memory and tool_history
    and ultimately answers the user's question precisely and accurately.
    Your rewritten query will be used to fetch information with search tools such as
    semantic search and keyword search.
    Please understand the information gap between the currently known information and
    the target problem.
    DON’T generate queries which has been retrieved or answered.
    """

    role_prompt: str = dspy.InputField()
    current_user_message: str = CURRENT_USER_MESSAGE_FIELD
    conversation_history: str = CONVERSATION_HISTORY_FIELD
    conversation_summary: str = CONVERSATION_SUMMARY_FIELD
    tool_history: str = TOOL_HISTORY_FIELD
    tool_summary: str = TOOL_SUMMARY_FIELD
    rewritten_query: str = dspy.OutputField(
        desc="The new, more specific query that you've written."
    )


class QueryRewrite(dspy.Module):
    def __init__(self):
        super().__init__()
        self.rewritten_query = dspy.Predict(QueryRewriteSignature)
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 2 / 15,
            "conversation_summary": 1 / 15,
            "tool_history": 5 / 15,
            "tool_summary": 1 / 15,
        }

    def get_token_limits(self) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.rewritten_query))
        )

    def forward(
        self,
        current_user_message: str,
        conversation_memory: ConversationMemory,
        tool_memory: ToolMemory,
    ):
        with (
            config.tracer.start_as_current_span("Query Rewrite")
            if hasattr(config, "tracer")
            else nullcontext()
        ) as span:
            span.set_attribute(
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                OpenInferenceSpanKindValues.CHAIN.value,
            )

            rewrite_inputs = dict(
                current_user_message=current_user_message,
                conversation_history=conversation_memory.history_str(),
                conversation_summary=conversation_memory.summary,
                tool_history=tool_memory.history_str(),
                tool_summary=tool_memory.summary,
            )
            rewrite_inputs = truncate_tokens_all(
                rewrite_inputs, self.get_token_limits()
            )
            rewrite_inputs["role_prompt"] = ROLE_PROMPT
            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(rewrite_inputs),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            rewritten_query = self.rewritten_query(**rewrite_inputs).rewritten_query
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, rewritten_query)
            span.set_status(Status(StatusCode.OK))
            return dspy.Prediction(rewritten_query=rewritten_query)
