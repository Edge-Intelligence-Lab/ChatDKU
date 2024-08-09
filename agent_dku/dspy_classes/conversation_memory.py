from pydantic import BaseModel, ConfigDict
from utils import (
    strs_fit_max_tokens_reverse,
    token_limit_ratio_to_count,
    truncate_tokens_all,
)
from dspy_common import get_template, custom_cot_rationale
from dspy_classes.prompt_settings import ROLE_PROMPT
import dspy


class ConversationMemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    content: str


def make_compress_conversation_memory_signature():
    fields = {
        "history_to_discard": (
            str,
            dspy.InputField(
                desc=(
                    "The conversation messages that would be removed from your Conversation History in JSON Lines format. "
                    "Each line specifies the role and content of the message."
                )
            ),
        ),
        "previous_summary": (
            str,
            dspy.InputField(
                desc="Previous summary of the discarded Conversation History. Might be empty.",
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
        "You have a Conversation History storing all the conversations between user "
        "and you, the assistant."
        "Your Conversation History has become too long, so the oldest entries have to be discarded. "
        "You keep a Summary of the discarded conversation history. "
        "Given the History To Discard and Previous Summary, update the Summary. "
        "Use Markdown in Summary. "
    )

    return dspy.make_signature(
        fields,
        ROLE_PROMPT + "\n\n" + instruction,
        "CompressConversationMemorySignature",
    )


CompressConversationMemorySignature = make_compress_conversation_memory_signature()


class ConversationMemory(dspy.Module):
    def __init__(self):
        super().__init__()
        self.compressor = dspy.ChainOfThought(
            CompressConversationMemorySignature, rationale_type=custom_cot_rationale
        )
        self.history: list[ConversationMemoryEntry] = []
        self.summary: str = ""
        self.token_ratios: dict[str, float] = {
            "history_to_discard": 2 / 4,
            "previous_summary": 1 / 4,
        }

    def get_token_limits(self) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.compressor))
        )

    def forward(self, role: str, content: str, max_history_size: int = 1000):
        self.history.append(ConversationMemoryEntry(role=role, content=content))

        min_index = strs_fit_max_tokens_reverse(
            [i.model_dump_json() for i in self.history],
            "\n",
            max_history_size,
        )
        if min_index > 0:
            compressor_inputs = dict(
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
