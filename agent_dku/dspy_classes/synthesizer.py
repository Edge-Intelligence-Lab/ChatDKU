#!/usr/bin/env python3
import dspy

from dspy_classes.prompt_settings import CURRENT_USER_MESSAGE_FIELD, ROLE_PROMPT


def make_synthesizer_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "tool_memory": (
            str,
            dspy.InputField(
                desc="Memory of what you have learned from using one or more tools.",
                format=lambda x: x,
            ),
        ),
        "response": (
            str,
            dspy.OutputField(desc="You response to the Current User Message."),
        ),
    }

    # instruction = "Your current task is to answer the Current User Message according to your Tool Memory."
    instruction = (
        "State the sources of all contexts referenced, include links in Markdown if availble. "
        "Be organized and use bullet points if needed. "
        "The contexts might contain unrelated information or non-DKU resources. "
        "Always prefer DKU resources first. "
        "You may include other resources (including even Duke resources) only as "
        "a second option unless directly asked, or that resource is clearly "
        "available to the DKU community via means such as a partnership with DKU. "
        "For you to appear more human to the user, all the context given should be "
        "treated as your internal knowledge. "
        'Thus, never use phrases like "based on the provided context". '
        "Your internal operation should also not be transparent to the user, "
        # 'so you should not mention phrases like "I\'ve refined my answer".'
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "SynthesizerSignature"
    )


SynthesizerSignature = make_synthesizer_signature()
