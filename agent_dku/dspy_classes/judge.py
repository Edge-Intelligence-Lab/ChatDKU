import dspy
from utils import token_limit_ratio_to_count, truncate_tokens_all
from dspy_common import get_template, custom_cot_rationale
from dspy_classes.conversation_memory import ConversationMemory
from dspy_classes.tool_memory import ToolMemory
from dspy_classes.prompt_settings import (
    CURRENT_USER_MESSAGE_FIELD,
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    TOOL_HISTORY_FIELD,
    TOOL_SUMMARY_FIELD,
    ROLE_PROMPT,
    VERBOSE,
)


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
                    'If you can answer the question, please reply with "Yes" directly; '
                    'if you cannot and need more information, please reply with "No" directly.'
                )
            ),
        ),
    }

    instruction = (
        "Judging based solely on the your system prompt and the information given below, "
        "and without allowing for inference, are you able to completely and accurately "
        "respond to the Current User Message?"
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
        judge_inputs = dict(
            current_user_message=current_user_message,
            conversation_history="\n".join(
                [i.model_dump_json() for i in conversation_memory.history]
            ),
            conversation_summary=conversation_memory.summary,
            tool_history="\n".join([i.model_dump_json() for i in tool_memory.history]),
            tool_summary=tool_memory.summary,
        )
        judge_inputs = truncate_tokens_all(judge_inputs, self.get_token_limits())
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
        return dspy.Prediction(judgement=(judgement_str == "Yes"))
