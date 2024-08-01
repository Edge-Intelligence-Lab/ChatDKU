#!/usr/bin/env python3
from pydantic import BaseModel
from typing import Any

import dspy

from dspy_common import custom_cot_rationale
from dspy_classes.prompt_settings import CURRENT_USER_MESSAGE_FIELD, ROLE_PROMPT

def make_update_tool_memory_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "tool_specification": (
            str,
            dspy.InputField(
                desc=(
                    "The specification of the tool you just called in JSON. "
                    "It includes the tool's name, description, and a list of "
                    "its parameters with descriptions for each parameter."
                ),
                format=lambda x: x,
            ),
        ),
        "tool_called": (
            str,
            dspy.InputField(
                desc=(
                    "The name of the tool and the parameters you gave to the tool "
                    "you just called in JSON."
                ),
                format=lambda x: x,
            ),
        ),
        "result": (
            str,
            dspy.InputField(
                desc=("The result returned from the tool you just called.")
            ),
        ),
        "previous_tool_memory": (
            str,
            dspy.InputField(
                desc=(
                    "Memory of what you have learned previously from the tools. "
                    "It would be empty if you have not called any tools previously."
                ),
                format=lambda x: x,
            ),
        ),
        "tool_memory_to_append": (
            str,
            dspy.OutputField(
                desc="What you want to append to your Tool Memory.",
                format=lambda x: x,
            ),
        ),
    }

    instruction = (
        "You have a Tool Memory storing all the information you learned from using "
        "multiple tools that would be useful for answering the Current User Message. "
        "You just called a tool and the result it returned would be provided. "
        "Your current task is to append to your Tool Memory with what you "
        "learned from the tool you just called and what you want to emphasize"
        "in the Previous Tool Memory. "
        "Note that older Tool Memory would be forgotten if they become too long. "
        "In the future, you would be asked to respond to the Current User Message "
        "with only your Tool Memory. "
        "Therefore, you should make it comprehensive enough so that it could "
        "be understood by you on its own."
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "UpdateToolMemorySignature"
    )


UpdateToolMemorySignature = make_update_tool_memory_signature()


class ToolMemory(dspy.Module):
    def reset(self):
        self.tools_called = []
        self.tool_plan = []
        # Observation: In a lot of times (but not always), Llama 3/3.1 would use
        # JSON to organize its own memory. However, it appears to actually
        # perform better when NOT using JSON. As the LLM tend to drop some of
        # previous memory when updating a memory in JSON format.
        # TODO: Offer a better memory structure.
        #
        # TODO: It might be better to only store what the LLM has learned from the
        # current tool call instead of also having to emphasize what it thought
        # to be important in the past memory. Then, when the tool memory begins
        # to exceed the context window. Those overflowing memory would be summarized
        # again.
        self.memory = ""

    def __init__(self):
        super().__init__()
        self.reset()
        self.update_tool_memory = dspy.ChainOfThought(
            UpdateToolMemorySignature, rationale_type=custom_cot_rationale
        )

    def forward(
        self,
        current_user_message: str,
        schema: dict[str, Any],
        calls: list[BaseModel],
        result: str,
    ):
        self.tools_called.append(calls[0])
        self.tool_plan = calls[1:].copy()
        self.memory += (
            "##########\n"
            + self.update_tool_memory(
                current_user_message=current_user_message,
                tool_specification=str(schema),
                tool_called=calls[0].model_dump_json(),
                result=result,
                previous_tool_memory=self.memory,
            ).tool_memory_to_append
        )
