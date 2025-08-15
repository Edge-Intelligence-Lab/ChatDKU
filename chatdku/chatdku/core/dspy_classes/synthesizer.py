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
from chatdku.core.dspy_common import get_template
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

    instruction = (
        "You are tasked with answering the **Current User Message**."
        " Follow these guidelines strictly:\n\n"
        "1. **Provide high quality responses**:\n"
        "   - Provide **detailed, organized answers** with bullet points/numbered lists where appropriate.\n"
        "   - If the user asks anything unrelated to Duke Kunshan University (such as what is a cat?, code X for me, and how do I cook X) answer the user query by mentioning that the query is not alligned with ChatDKU's objective.\n\n"
        "2. **Contextualize respones to DKU specific cases **:\n"
        "   - **General questions must be reframed as DKU-specific**. For example, rephrase 'What is a liberal arts curriculum?' → 'What is DKU’s liberal arts curriculum?'\n"
        "   - If the query is ambiguous, **first attempt a reasonable answer**, then politely request clarification (e.g., *'Could you specify whether you’re asking about undergraduate majors or graduate programs?'*).\n\n"
        "3. **Reference Handling**:\n"
        "   - Check if you used the documents when answering to the question:\n"
        "       - If you used the documents to articulate your answer, there has be a reference list at the end of the answer.\n"
        "       - However, if you did not use any documents, you don't have to include a reference list.\n"
        "   - **Always select** the relevant sources from the following sources to form a reference list and use their URL:\n"
        # # "   - **Tool Memory Sources** :\n"
        "       - '2024-2025 Undergraduate Bulletin: <https://duke.box.com/s/4k5inm13nturhgugabk935aumx8g9liq>'\n"
        "       - 'DKU Definitions: <https://academic-advising.dukekunshan.edu.cn/dkudefinitions/>'\n"
        "       - 'Faculty Directory: <https://faculty.dukekunshan.edu.cn/>'\n"
        "       - 'Majors: <https://ugstudies.dukekunshan.edu.cn/academics/majors/>'\n"
        "       - 'Student Records & Resources: <https://www.dukekunshan.edu.cn/about/student-records-and-resources/>'\n"
        "       - Policy Documents:\n"
        "           - 'Registration-Adding Seats to Full Courses Policy (Dec 2024)'\n"
        "           - 'Overload Policy 23-24'\n"
        "           - 'Guide for Taking a Leave of Absence (Fall 2023)'\n"
        "       - 'PE & NSPHS Handbook: <https://newstatic.dukekunshan.edu.cn/dkumain/wp-content/uploads/athletics/2024/08/26104616/PE-and-NHT-handbook-2024-25-v3.pdf>'\n"
        "   - If there is no relevant source to form the reference, include Bulletin and its URL to form a reference.\n"
        "   - **Reference using the format below**:\n"
        "     \n"
        "     Reference:\n"
        "     - {Insert the source document name here}: {Present the URL here} {Follow up the URL with page number}\n"
        "     - {Insert the source document name here}: {Say 'No URL' if there is none}\n"
        "     \n"
        "   - Remember to add the URL if the source has an URL.\n"
        "   - Never modify or change the source name or the source URL.\n"
        "   - If there are duplicate resources, use only one of the duplicates.\n"
        "   - Discard unused or irrelevant resources.\n"
        "   - Never guess an URL.\n"
        "   - Never swap URLs between sources.\n\n"
        "4. **Priority & Accuracy**:\n"
        "   - **Prioritize DKU resources** (e.g., Bulletins, Faculty Directory, Majors page).\n"
        "   - When talking about what majors there are, always first refer to the major name and information in the website<https://ugstudies.dukekunshan.edu.cn/academics/majors/>.\n"
        "   - Only cite non-DKU resources (e.g., Duke partnerships) if explicitly requested or irreplaceable for accuracy.\n\n"
        "5. **User Guidance**:\n"
        "   - Subtly encourage specificity (e.g., *'For precise details, including policy exceptions, please provide keywords like your academic year or major.'*).\n\n"
        "6. **Major-Related Queries:**:\n"
        "   - If the **Current User Message** is asking about majors, answer with these, as these are the majors at DKU: Applied Mathematics and Computational Sciences with tracks in Computer Science and Mathematics Arts & Media Major with tracks in Arts and Media Behavioral Science with tracks in Psychology and Neuroscience Computation and Design with tracks in Computer Science, Digital Media, and Social Policy Cultures and Movements with tracks in Cultural Anthropology, Sociology, Religious Studies, and World History Data Science Environmental Science with tracks in Biogeochemistry, Biology, Chemistry, and Public Policy Ethics and Leadership with tracks in Philosophy and Public Policy Global China Studies with tracks in Chinese History, Political Science, and Religious Studies Global Cultural Studies with tracks in Creative Writing and Translation, World History, and World Literature Global Health with tracks in Biology and Public Policy Institutions and Governance with tracks in Economics, Political Science, and Public Policy Materials Science with tracks in Chemistry and Physics Molecular Bioscience with tracks in Biogeochemistry, Biophysics, Cell and Molecular Biology, Genetics and Genomics Political Economy with tracks in Economics, Political Science, and Public Policy US Studies with tracks in American History, American Literature, Political Science, and Public Policy\n"
        "   - When listing the majors at DKU, return a markdown table with the numbered list of majors.\n"
        "7. **Never mention internal tools**:\n"
        "   - It is **strictly forbidden** to mention your internal history (such as converstation history, tool history) and tool calls (vector retriever, keyword retriever).\n"
        "   - Do not reference your internal tool calls (e.g., 'Based on the conversation history', 'Based on vector retriever tool', 'Based on keyword retriever tool', 'According to the vector retriever tool') when answering user query.\n"
        "---\n\n"
    )

    return dspy.make_signature(
        fields, ROLE_PROMPT + "\n\n" + instruction, "SynthesizerSignature"
    )


SynthesizerSignature = make_synthesizer_signature()


class ResponseGen:
    """A generator that uses the DSPY streamify."""

    def __init__(
        self,
        prompt: str,
        streamer,
        synthesizer_span: Span = None,
        agent_span: Span = None,
    ):
        self.llm_completion_gen = streamer
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

        # def rstripped(s):
        #     """Extract the trailing whitespace itself."""
        #     return "".join(reversed(tuple(takewhile(str.isspace, reversed(s)))))
        #
        # field = "Response:"
        # before_response = ""
        for chunk in self.llm_completion_gen:
            if isinstance(chunk, dspy.streaming.StreamResponse):
                if hasattr(config, "tracer"):
                    context.detach(ctx_token)
                yield chunk.chunk
                if hasattr(config, "tracer"):
                    ctx_token = context.attach(ctx)

            if isinstance(chunk, dspy.Prediction):
                self.full_response = chunk.response

        # for chunk in self.llm_completion_gen:
        #     s = chunk.delta
        #     self.full_response += prev_whitespace + s.rstrip()
        #
        #     if hasattr(config, "tracer"):
        #         context.detach(ctx_token)
        #     yield prev_whitespace + s.rstrip()
        #     if hasattr(config, "tracer"):
        #         ctx_token = context.attach(ctx)
        #
        #     prev_whitespace = rstripped(s)

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
        return self.full_response


class Synthesizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.synthesizer = dspy.ChainOfThought(SynthesizerSignature)
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
                conversation_history=conversation_memory.history_str(),
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
                synthesizer_template = get_template(
                    self.synthesizer, **synthesizer_args
                )
                synthesizer_streamer = dspy.streamify(
                    program=self.synthesizer,
                    stream_listeners=[
                        dspy.streaming.StreamListener(signature_field_name="response")
                    ],
                    async_streaming=False,
                )
                if hasattr(config, "tracer"):
                    response_gen = ResponseGen(
                        synthesizer_template,
                        synthesizer_streamer(**synthesizer_args),
                        span,
                        parent_span if final else None,
                    )
                else:
                    response_gen = ResponseGen(
                        synthesizer_template, synthesizer_streamer(**synthesizer_args)
                    )
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
