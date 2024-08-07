from pydantic import BaseModel, ConfigDict
from utils import strs_fit_max_tokens_reverse
from dspy_common import custom_cot_rationale
from dspy_classes.prompt_settings import CURRENT_USER_MESSAGE_FIELD, ROLE_PROMPT
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
    # FIXME: Should not use fixed history size
    MAX_HISTORY_SIZE = 4000

    def __init__(self):
        super().__init__()
        self.compressor = dspy.ChainOfThought(
            CompressConversationMemorySignature, rationale_type=custom_cot_rationale
        )
        self.history: list[ConversationMemoryEntry] = []
        self.summary: str = ""

    def forward(self, role: str, content: str):
        self.history.append(ConversationMemoryEntry(role=role, content=content))

        min_index = strs_fit_max_tokens_reverse(
            [i.model_dump_json() for i in self.history],
            "\n",
            self.MAX_HISTORY_SIZE,
        )
        if min_index > 0:
            self.summary = self.compressor(
                history_to_discard="\n".join(
                    [i.model_dump_json() for i in self.history[:min_index]]
                ),
                previous_summary=self.summary,
            ).current_summary
            self.history = self.history[min_index:]
