#!/usr/bin/env python3
from pydantic import BaseModel, ConfigDict
from llama_index.core import Settings

import dspy
from dspy_common import custom_cot_rationale
from serialization import NameParams
from dspy_classes.prompt_settings import CURRENT_USER_MESSAGE_FIELD, ROLE_PROMPT


class ToolMemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name_params: NameParams
    result: str


def make_compress_tool_memory_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "history_to_discard": (
            str,
            dspy.InputField(
                desc=(
                    "The tool calls that would be removed from your Tool History in JSON Lines format. "
                    "Each line specifies the name and parameters of the tool and its result. "
                    "You should extract relevant information from these tool calls."
                )
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
    # FIXME: Should not use fixed history size
    MAX_HISTORY_SIZE = 4000

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
        self.reset()

    def forward(
        self,
        current_user_message: str,
        calls: list[NameParams],
        result: str,
    ):
        self.history.append(ToolMemoryEntry(name_params=calls[0], result=result))
        self.plan = calls[1:].copy()

        history_strs = [i.model_dump_json() for i in self.history]
        history_lens = [len(Settings.tokenizer(i)) for i in history_strs]
        min_index = len(history_lens)
        cum_sum = 0
        for i in reversed(range(len(history_lens))):
            cum_sum += history_lens[i]
            if cum_sum > self.MAX_HISTORY_SIZE:
                break
            min_index = i

        if min_index > 0:
            self.summary = self.compressor(
                current_user_message=current_user_message,
                history_to_discard="\n".join(history_strs[:min_index]),
                previous_summary=self.summary,
            ).current_summary
            self.history = self.history[min_index:]
