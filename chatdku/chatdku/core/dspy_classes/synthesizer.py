from itertools import takewhile

from llama_index.core import Settings

import dspy

from contextlib import nullcontext
from openinference.instrumentation import safe_json_dumps
from opentelemetry.trace import (
    Status,
    StatusCode,
    use_span,
    get_current_span,
    Span,
    set_span_in_context,
)
from opentelemetry import context
from openinference.semconv.trace import (
    SpanAttributes,
    OpenInferenceSpanKindValues,
    OpenInferenceMimeTypeValues,
)

from chatdku.core.utils import token_limit_ratio_to_count, truncate_tokens_all
from chatdku.core.dspy_common import custom_cot_rationale, get_template
from chatdku.core.dspy_classes.prompt_settings import (
    CURRENT_USER_MESSAGE_FIELD,
    CONVERSATION_HISTORY_FIELD,
    CONVERSATION_SUMMARY_FIELD,
    TOOL_HISTORY_FIELD,
    TOOL_SUMMARY_FIELD,
    ROLE_PROMPT,
)
from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.plan import ToolMemory

from chatdku.config import config

from datetime import date


def make_synthesizer_signature():

    fields = {
        "current_user_message": (str, CURRENT_USER_MESSAGE_FIELD),
        "conversation_history": (str, CONVERSATION_HISTORY_FIELD),
        "conversation_summary": (str, CONVERSATION_SUMMARY_FIELD),
        "tool_history": (str, TOOL_HISTORY_FIELD),
        "tool_summary": (str, TOOL_SUMMARY_FIELD),
        "response": (
            str,
            dspy.OutputField(desc="You response to the Current User Message."),
        ),
    }
    current_date = date.today()

    # instruction = "Your current task is to answer the Current User Message according to your Tool Memory."
    instruction = (
        "Your current task is to answer the Current User Message according to your Tool Memory."
        # "Your answer should be as detailed as possible."
        "Your answer should be be organized and use bullet points if needed."
        # "Only use DKU resources in the database. ""
        "Always and only select the markdown below (1-10) in the reference list:"
        "1. [2024-2025 Undergraduate Bulletin](https://duke.app.box.com/s/u6ajvjuo2yocn57rld4ztu6jrrdxfn0n);"
        "2. [DKU Definitions page](https://academic-advising.dukekunshan.edu.cn/dkudefinitions/);"
        "3. [Faculty Directory](https://faculty.dukekunshan.edu.cn/);"
        "4. Understanding Major Declaration;"
        "5. Registration-Adding Seats to Full Courses Policy Updated, December 2024;"
        "6. Registration Planning Guide + Cheat Sheet;"
        "7. Overload Policy 23-24;"
        "8. Guide for Taking a Leave of Absence - Updated Fall 2023;"
        "9. CRNC FAQ for Advisors;10. Advising FAQ (12-19-24 Update)"
        "Please delete the references that are not relevant to the query."
        # "The contexts might contain unrelated information or non-DKU resources. "
        # "Always prefer DKU resources first. "
        # "You may include other resources (including even Duke resources) only as "
        # "a second option unless directly asked, or that resource is clearly "
        # "available to the DKU community via means such as a partnership with DKU. "
        # "The source of contexts is contained in the url in metadata,"
        # "Include the urls to the sources used in your answer at the end, like 'reference links:'. "
        # "Do not include the urls to the sources that you did not use in your answer. "
        # "Links should be in markdown format for easy clicking, with the link text accurately reflecting the URL’s content."
        # "summary of the link, make sure the text is accurate about the url, and please don't print duplicate links. "
        # "make sure the reference link you offer is the accurate copy from your database. "
        # "If you see 'no url' for a source, do not provide the link. "
        # "Do not guess the url."
        # "Do not use the url of one source for another source. "
        "Your internal operation should also not be transparent to the user, "
        '"do not include phrases like "Based on the conversation history", '
        '"Based on the information retrieved from the Tool History and Conversation History", "According to the tool history" in your answer. '

        # "When you're asked a general question, automatically change it to something DKU related, "
        # "like 'what does CTL do?' to 'what does CTL do at DKU?' "
        # "If the Current User Message is ambiguous, you may first try to answer it to the best extent, then ask the user for further clarifications. "
        # "Additionally, you should point out the cases where the information in Tool Memory does not "
        ### time ...
        f"Today's date is {current_date}. For timeliness issues, please consider more relevant context closer to the current date."
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "SynthesizerSignature"
    )


SynthesizerSignature = make_synthesizer_signature()


class ResponseGen:
    """A generator that extracts `response` field and strips whitespace
    given the generator for the entire LLM completion.
    """

    def __init__(
        self, prompt: str, synthesizer_span: Span = None, agent_span: Span = None
    ):
        self.llm_completion_gen = Settings.llm.stream_complete(prompt)
        if hasattr(config, "tracer"):
            self.span = config.tracer.start_span(
                "LLM", context=set_span_in_context(synthesizer_span)
            )
            self.span.set_attributes(
                {
                    SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.LLM.value,
                    SpanAttributes.INPUT_VALUE: prompt,
                    SpanAttributes.LLM_MODEL_NAME: config.llm,
                }
            )
            self.synthesizer_span = synthesizer_span
            self.agent_span = agent_span
        self.full_response = ""

    def __iter__(self):
        # When streaming the response, it starts a new span inside `synthesizer_span`
        # and ends `synthesizer_span` on completion.
        # Additionally, as the "lifetime" of the agent actually ends when streaming is complete,
        # so the span of `agent_span` is also ended by `ResponseGen` if it is the final response.
        if hasattr(config, "tracer"):
            ctx = set_span_in_context(self.span)
            ctx_token = context.attach(ctx)

        def rstripped(s):
            """Extract the trailing whitespace itself."""
            return "".join(reversed(tuple(takewhile(str.isspace, reversed(s)))))

        field = "Response:"
        before_response = ""
        for r in self.llm_completion_gen:
            before_response += r.delta
            offset = before_response.find(field)
            if offset != -1:
                s = before_response[offset + len(field) :]
                if s.strip():
                    self.full_response += s.strip()

                    if hasattr(config, "tracer"):
                        context.detach(ctx_token)
                    yield s.strip()
                    if hasattr(config, "tracer"):
                        ctx_token = context.attach(ctx)

                    prev_whitespace = rstripped(s)
                    break

        for r in self.llm_completion_gen:
            s = r.delta
            self.full_response += prev_whitespace + s.rstrip()

            if hasattr(config, "tracer"):
                context.detach(ctx_token)
            yield prev_whitespace + s.rstrip()
            if hasattr(config, "tracer"):
                ctx_token = context.attach(ctx)

            prev_whitespace = rstripped(s)

        if hasattr(config, "tracer"):
            context.detach(ctx_token)
            self.span.set_attribute(SpanAttributes.OUTPUT_VALUE, self.full_response)
            self.span.set_status(Status(StatusCode.OK))
            self.span.end()
            self.synthesizer_span.set_attribute(
                SpanAttributes.OUTPUT_VALUE, self.full_response
            )
            self.synthesizer_span.set_status(Status(StatusCode.OK))
            self.synthesizer_span.end()
            if self.agent_span:
                self.agent_span.set_attribute(
                    SpanAttributes.OUTPUT_VALUE, self.full_response
                )
                self.agent_span.set_status(Status(StatusCode.OK))
                self.agent_span.end()

    def get_full_response(self) -> str:
        # Make sure the entire response is read
        for _ in self:
            pass
        return self.full_response


class Synthesizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.synthesizer = dspy.ChainOfThought(
            SynthesizerSignature, rationale_type=custom_cot_rationale
        )
        self.token_ratios: dict[str, float] = {
            "current_user_message": 2 / 15,
            "conversation_history": 2 / 15,
            "conversation_summary": 1 / 15,
            "tool_history": 5 / 15,
            "tool_summary": 1 / 15,
        }

    def get_token_limits(self) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.synthesizer))
        )

    def forward(
        self,
        current_user_message: str,
        conversation_memory: ConversationMemory,
        tool_memory: ToolMemory,
        streaming: bool,
        final: bool = False,  # If final call to synthesizer, then also end agent's span when tracing
    ):
        if hasattr(config, "tracer"):
            span = config.tracer.start_span("Synthesizer")
            span.set_attribute(
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                OpenInferenceSpanKindValues.CHAIN.value,
            )

        with use_span(span) if hasattr(config, "tracer") else nullcontext():
            synthesizer_args = dict(
                current_user_message=current_user_message,
                conversation_history="\n".join(
                    [i.model_dump_json() for i in conversation_memory.history]
                ),
                conversation_summary=conversation_memory.summary,
                # TODO: Might want to unify conversion to string for `ToolMemory`
                tool_history="\n\n###\n\n".join(
                    [i.model_dump_json() for i in tool_memory.history]
                ),
                tool_summary=tool_memory.summary,
            )
            synthesizer_args = truncate_tokens_all(
                synthesizer_args, self.get_token_limits()
            )
            span.set_attributes(
                {
                    SpanAttributes.INPUT_VALUE: safe_json_dumps(synthesizer_args),
                    SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
                }
            )

        if streaming:
            if hasattr(config, "tracer"):
                parent_span = get_current_span()

            with use_span(span) if hasattr(config, "tracer") else nullcontext():
                # A hacky way to stream the final response synthesis LLM call.
                # The synthesizer module is first converted to a prompt string.
                # Then the LLM is called manually, and the generator returned is wrapped
                # to extract only the `response` field.
                #
                # FIXME: Contribute streaming support to DSPy
                # Also see: https://github.com/stanfordnlp/dspy/issues/338
                synthesizer_template = get_template(
                    self.synthesizer, **synthesizer_args
                )
                if hasattr(config, "tracer"):
                    response_gen = ResponseGen(
                        synthesizer_template, span, parent_span if final else None
                    )
                else:
                    response_gen = ResponseGen(synthesizer_template)
                return dspy.Prediction(response=response_gen)

        else:
            with (
                use_span(span, end_on_exit=True)
                if hasattr(config, "tracer")
                else nullcontext()
            ):
                response = self.synthesizer(**synthesizer_args).response
                span.set_attribute(SpanAttributes.OUTPUT_VALUE, response)
                span.set_status(Status(StatusCode.OK))
                return dspy.Prediction(response=response)
