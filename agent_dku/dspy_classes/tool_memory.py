from pydantic import BaseModel, ConfigDict

import dspy
from dspy_common import get_template, custom_cot_rationale
from utils import (
    NameParams,
    strs_fit_max_tokens_reverse,
    token_limit_ratio_to_count,
    truncate_tokens_all,
)
from dspy_classes.prompt_settings import (
    CURRENT_USER_MESSAGE_FIELD,
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    ROLE_PROMPT,
)
from dspy_classes.conversation_memory import ConversationMemory


class ToolMemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name_params: NameParams
    result: str


def make_compress_tool_memory_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "conversation_history": (str, CONVERSATION_HISTORY_FIELD),
        "conversation_summary": (str, CONVERSATION_SUMMARY_FIELD),
        "history_to_discard": (
            str,
            dspy.InputField(
                desc=(
                    "The tool calls that would be removed from your Tool History in JSON Lines format. "
                    "Each line specifies the name and parameters of the tool and its result. "
                    "You should extract relevant information from these tool calls."
                ),
                format=lambda x: x,
            ),
        ),
        "previous_summary": (
            str,
            dspy.InputField(
                desc="Previous summary of the discarded Tool History. Might be empty.",
                format=lambda x: x,
            ),
        ),
        "current_summary": (
            str,
            dspy.OutputField(
                desc="Your updated summary.",
            ),
        ),
    }

    instruction = (
        "You have a Tool History storing all the tool calls you made for answering "
        "the Current User Message. "
        "Your Tool History has become too long, so the oldest entries have to be discarded. "
        "You keep a Summary of the discarded tool history. "
        "Given the History To Discard and Previous Summary, update the Summary. "
        "Remove the information not relevant to answer the Current User Message "
        "and keep all the relevant information if possible. "
        "Use Markdown in Summary. "
        "Store the sources that you retrieved these information from."
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "CompressToolMemorySignature"
    )


CompressToolMemorySignature = make_compress_tool_memory_signature()


class ToolMemory(dspy.Module):
    def reset(self):
        # Tools already called, with names, parameters, and results
        self.history: list[ToolMemoryEntry] = []
        # Tools planned to be called, with names and parameters
        self.plan: list[NameParams] = []
        # Summary of old history that exceeds `MAX_HISTORY_SIZE`
        self.summary: str = ""

    def __init__(self):
        super().__init__()
        self.compressor = dspy.ChainOfThought(
            CompressToolMemorySignature, rationale_type=custom_cot_rationale
        )
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 14,
            "conversation_history": 2 / 14,
            "conversation_summary": 1 / 14,
            "history_to_discard": 5 / 14,
            "previous_summary": 1 / 14,
        }
        self.reset()

    def get_token_limits(self) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.compressor))
        )

    def forward(
        self,
        current_user_message: str,
        conversation_memory: ConversationMemory,
        calls: list[NameParams],
        result: str,
        max_history_size: int = 1000,
    ):
        self.history.append(ToolMemoryEntry(name_params=calls[0], result=result))
        self.plan = calls[1:].copy()

        min_index = strs_fit_max_tokens_reverse(
            [i.model_dump_json() for i in self.history],
            "\n",
            max_history_size,
        )
        if min_index > 0:
            compressor_inputs = dict(
                current_user_message=current_user_message,
                conversation_history="\n".join(
                    [i.model_dump_json() for i in conversation_memory.history]
                ),
                conversation_summary=conversation_memory.summary,
                history_to_discard="\n".join(
                    [i.model_dump_json() for i in self.history[:min_index]]
                ),
                previous_summary=self.summary,
            )
            compressor_inputs = truncate_tokens_all(
                compressor_inputs, self.get_token_limits()
            )

            self.summary = self.compressor(**compressor_inputs).current_summary
            self.history = self.history[min_index:]
