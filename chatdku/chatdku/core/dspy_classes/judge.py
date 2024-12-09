import dspy

from contextlib import nullcontext
from openinference.instrumentation import safe_json_dumps
from opentelemetry.trace import Status, StatusCode
from openinference.semconv.trace import (
    SpanAttributes,
    OpenInferenceSpanKindValues,
    OpenInferenceMimeTypeValues,
)

from chatdku.core.utils import token_limit_ratio_to_count, truncate_tokens_all
from chatdku.core.dspy_common import get_template, custom_cot_rationale
from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.tool_memory import ToolMemory
from chatdku.core.dspy_classes.prompt_settings import (
    CURRENT_USER_MESSAGE_FIELD,
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    TOOL_HISTORY_FIELD,
    TOOL_SUMMARY_FIELD,
    ROLE_PROMPT,
    VERBOSE,
)

from chatdku.config import config


def make_judge_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "conversation_history": (str, CONVERSATION_HISTORY_FIELD),
        "conversation_summary": (str, CONVERSATION_SUMMARY_FIELD),
        "tool_history": (str, TOOL_HISTORY_FIELD),
        "tool_summary": (str, TOOL_SUMMARY_FIELD),
        "judgement": (
            str,
            dspy.OutputField(
                desc=(
                    'If you should respond to the user, please reply with "Yes" directly; '
                    'if you think you should look for more information, please reply with "No" directly.'
                )
            ),
        ),
    }

    instruction = (
        "You are capable of making tool calls to retrieve relevant information for answering "
        "the Current User Message. "
        "The information you already learned from the tool calls is given in the Tool History.\n\n"
        "You current task is to judge, base solely on the system prompt and the information given below, "
        "whether should respond to the Current User Message with these information, "
        "or should you look for more information by making more tool calls. "
        "You should respond to the user when either "
        "(a) the given information is sufficient for answer the Current User Message or "
        "(b) the Current User Message is ambiguous to the extent that further tool calls would not be "
        "helpful for answering it. "
        # This might seem a bit extraneous for now, but it appears that the LLM needs a stronger nudge
        # on case (b) to say "Yes".
        # It should be done by better prompt engineering/few-shot examples in the future.
        "Note that you should respond to the user if (b) holds, where you should ask for clarifications "
        "as opposed to answering the question itself."
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "JudgeSignature"
    )


JudgeSignature = make_judge_signature()


class Judge(dspy.Module):
    def __init__(self):
        super().__init__()
        self.judge = dspy.ChainOfThought(
            JudgeSignature, rationale_type=custom_cot_rationale
        )
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 2 / 15,
            "conversation_summary": 1 / 15,
            "tool_history": 5 / 15,
            "tool_summary": 1 / 15,
        }

    def get_token_limits(self) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.judge))
        )

    def forward(
        self,
        current_user_message: str,
        conversation_memory: ConversationMemory,
        tool_memory: ToolMemory,
    ):
        with (
            config.tracer.start_as_current_span("Judge")
            if hasattr(config, "tracer")
            else nullcontext()
        ) as span:
            span.set_attribute(
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                OpenInferenceSpanKindValues.CHAIN.value,
            )

            judge_inputs = dict(
                current_user_message=current_user_message,
                conversation_history=conversation_memory.history_str(),
                conversation_summary=conversation_memory.summary,
                tool_history=tool_memory.history_str(),
                tool_summary=tool_memory.summary,
            )
            judge_inputs = truncate_tokens_all(judge_inputs, self.get_token_limits())
            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(judge_inputs),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

            judgement_str = self.judge(**judge_inputs).judgement

            dspy.Suggest(
                judgement_str in ["Yes", "No"],
                'Judgement should be either "Yes" or "No" (without quotes and first letter of each word capitalized).',
            )
            if judgement_str not in ["Yes", "No"]:
                if VERBOSE:
                    print(
                        'Judgement not "Yes" or "No" after retries, default to "No" (`False`).'
                    )
            judgement = judgement_str == "Yes"

            # FIXME: While OpenTelemetry allows Boolean values, Arize Phoenix has issue with it,
            # as there is a part of the code that assumes the attribute to be a string.
            # Here: https://github.com/Arize-ai/phoenix/blob/2eae8c5df25c4454352d4167b3435675db19ae75/src/phoenix/server/api/types/Span.py#L93
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, str(judgement))
            span.set_status(Status(StatusCode.OK))
            return dspy.Prediction(judgement=judgement)
