"""This is a DSPy class meant to first take a lcoation for the user profile, and update the user's profile based on the user's new query."""

import os
from pathlib import Path

import dspy
from chatdku.core.utils import token_limit_ratio_to_count, truncate_tokens_all
from chatdku.core.dspy_common import get_template
from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.tool_memory import ToolMemory
from chatdku.core.dspy_classes.prompt_settings import (
    CURRENT_USER_MESSAGE_FIELD,
    CONVERSATION_HISTORY_FIELD,
    TOOL_HISTORY_FIELD,
    TOOL_SUMMARY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    EXISTING_USER_PROFILE_FIELD,
    ROLE_PROMPT,
)

# from chatdku.config import config


def make_profiler_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "conversation_history": (str, CONVERSATION_HISTORY_FIELD),
        "tool_history": (str, TOOL_HISTORY_FIELD),
        "tool_summary": (str, TOOL_SUMMARY_FIELD),
        "conversation_summary": (str, CONVERSATION_SUMMARY_FIELD),
        "existing_profile": (str, EXISTING_USER_PROFILE_FIELD),
        "new_profile": (
            str,
            dspy.OutputField(
                desc=(
                    "Personal information about the user's identity in JSON format. "
                    "Fields to include are name, position (such as student or faculty member), department, etc. "
                    "If the user is an undergraduate student, include major, track (if applicable), year of study, and graduating term."
                    "Strictly keep formatting in JSON. "
                    "Add new fields that tell more about the user only when it's necessary. "
                    "Only include information about the USER. Do not add policy information or information unrelated to the user's identity."
                )
            ),
        ),
    }

    instruction = (
        "This is your current task: "
        "Based on the user's typed message, update their user profile with any new characteristics about the user to the existing user profile description for a more comprehensive understanding of the user so as to help give more relevant and specific answers to help the user. "
        "Include only personal facts that the user has personally stated in the current_user_message. "
    )

    return dspy.make_signature(
        fields,
        ROLE_PROMPT + "\n\n" + instruction,
        "ProfilerSignature",
    )


def get_user_profile(path: str, encoding: str = "utf-8") -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    try:
        with open(path, "r", encoding=encoding) as f:
            return f.read()
    except FileNotFoundError:
        Path(path).touch()
        return ""


class Profiler(dspy.Module):
    def __init__(self, profile_path):
        super().__init__()
        ProfilerSignature = make_profiler_signature()
        self.profile_path = profile_path
        self.profiler = dspy.ChainOfThought(ProfilerSignature)
        self.token_ratios: dict[str, float] = {
            "current_user_message": 6 / 15,
            "conversation_history": 1 / 15,
            "tool_summary": 1 / 15,
            "tool_history": 1 / 15,
            "conversation_summary": 1 / 15,
            "existing_profile": 5 / 15,
        }

    def get_token_limits(self) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.profiler))
        )

    def forward(
        self,
        profile_path: str,
        current_user_message: str,
        conversation_memory: ConversationMemory,
        tool_memory: ToolMemory,
    ):
        existing_profile = get_user_profile(profile_path)

        profiler_inputs = dict(
            current_user_message=current_user_message,
            conversation_history=conversation_memory.history_str(),
            conversation_summary=conversation_memory.summary,
            existing_profile=existing_profile,
            tool_history=tool_memory.history_str(),
            tool_summary=tool_memory.summary,
        )
        profiler_inputs = truncate_tokens_all(profiler_inputs, self.get_token_limits())

        # Process inputs using the DSPy model with the profiler signature
        updated_profile = self.profiler(**profiler_inputs).new_profile
        print("NEW PROFILE -> " + updated_profile)

        # Write the updated profile back to the file
        with open(self.profile_path, "w", encoding="utf-8") as f:
            f.write(updated_profile)

        return {"updated_profile": updated_profile}
