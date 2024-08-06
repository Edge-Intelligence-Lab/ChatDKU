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
        "Your current task is to answer the Current User Message according to your Tool Memory."
        "Your answer should be as detailed as possible, taking advantage of the relevant context in tool memory."
        "Your answer should be be organized and use bullet points if needed."
        "The contexts might contain unrelated information or non-DKU resources. "
        "Always prefer DKU resources first. "
        "You may include other resources (including even Duke resources) only as "
        "a second option unless directly asked, or that resource is clearly "
        "available to the DKU community via means such as a partnership with DKU. "
        "The origin of contexts is contained in the url in metadata,"
        "If you are using information from a context, include the url at the end of your answer so that the user can go back to the original file to verify the authenticity of the information."
        "Your answer needs to be as detailed as possible. All the contexts related to the Current User Message should be included in your answer."
        ### time ...
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "SynthesizerSignature"
    )


SynthesizerSignature = make_synthesizer_signature()
