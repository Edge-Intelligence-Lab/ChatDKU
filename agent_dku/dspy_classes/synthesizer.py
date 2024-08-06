#!/usr/bin/env python3

from itertools import takewhile

from llama_index.core import Settings

import dspy

from dspy_common import custom_cot_rationale, get_template
from dspy_classes.prompt_settings import (
    CURRENT_USER_MESSAGE_FIELD,
    TOOL_HISTORY_FIELD,
    TOOL_SUMMARY_FIELD,
    ROLE_PROMPT,
)
from dspy_classes.plan import ToolMemory


def make_synthesizer_signature():
    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "tool_history": (str, TOOL_HISTORY_FIELD),
        "tool_summary": (str, TOOL_SUMMARY_FIELD),
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


class Synthesizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.synthesizer = dspy.ChainOfThought(
            SynthesizerSignature, rationale_type=custom_cot_rationale
        )

    def forward(
        self, current_user_message: str, tool_memory: ToolMemory, streaming: bool
    ):
        if streaming:
            # A hacky way to stream the final response synthesis LLM call.
            # The synthesizer module is first converted to a prompt string.
            # Then the LLM is called manually, and the generator returned is wrapped
            # to extract only the "Response" field.
            #
            # TODO: Contribute streaming support to DSPy
            # Also see: https://github.com/stanfordnlp/dspy/issues/338

            synthesizer_template = get_template(
                self.synthesizer._predict,
                current_user_message=current_user_message,
                tool_history="\n".join(
                    [i.model_dump_json() for i in tool_memory.history]
                ),
                tool_summary=tool_memory.summary,
            )

            # input("Response is almost ready, press ENTER to begin streaming")

            def parse_gen():
                """
                A generator that returns the part after "Response:" and strips whitespace.
                """

                def rstripped(s):
                    """Extract the trailing whitespace itself."""
                    return "".join(reversed(tuple(takewhile(str.isspace, reversed(s)))))

                field = "Response:"
                gen = Settings.llm.stream_complete(synthesizer_template)
                before_response = ""
                for r in gen:
                    before_response += r.delta
                    offset = before_response.find(field)
                    if offset != -1:
                        s = before_response[offset + len(field) :]
                        if s.strip():
                            yield s.strip()
                            prev_whitespace = rstripped(s)
                            break

                for r in gen:
                    s = r.delta
                    yield prev_whitespace + s.rstrip()
                    prev_whitespace = rstripped(s)

            return dspy.Prediction(response=parse_gen())

        else:
            return self.synthesizer(
                current_user_message=current_user_message,
                tool_history="\n".join(
                    [i.model_dump_json() for i in tool_memory.history]
                ),
                tool_summary=tool_memory.summary,
            )
