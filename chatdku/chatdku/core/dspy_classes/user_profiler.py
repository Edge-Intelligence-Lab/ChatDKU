"""This is a DSPy class meant to first take a lcoation for the user profile, and update the user's profile based on the user's new query."""

import dspy

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
    EXISTING_USER_PROFILE_FIELD,
    ROLE_PROMPT,
)

from chatdku.config import config


def make_profiler_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "conversation_history": (str, CONVERSATION_HISTORY_FIELD),
        "conversation_summary": (str, CONVERSATION_SUMMARY_FIELD),
        "existing_user_profile": (str, EXISTING_USER_PROFILE_FIELD),
    }

    instruction = "Based on the user's typed message, append all new characteristics about the user to the existing user profile description for a more comprehensive understanding of the user so as to help give more relevant and specific answers to help the user. "

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "ProfilerSignature"
    )


ProfilerSignature = make_profiler_signature()


def get_user_profile(path: str, encoding: str = "utf-8"):
    try:
        with open(path, "r", encoding=encoding) as f:
            return f.read()
    except FileNotFoundError:
        return "User profile does not exist."


class Profiler(dspy.Module):
    def __init__(self, profile_path):
        super().__init__()
        self.profile_path = profile_path

    def forward(self, inputs: dict) -> dict:
        # Retrieve existing profile from file
        existing_profile = get_user_profile(self.profile_path)
        inputs.setdefault("existing_user_profile", existing_profile)

        # Process inputs using the DSPy model with the profiler signature
        updated_profile = dspy.call_model(ProfilerSignature, inputs)

        # Write the updated profile back to the file
        with open(self.profile_path, "w", encoding="utf-8") as f:
            f.write(updated_profile)

        return {"updated_profile": updated_profile}
