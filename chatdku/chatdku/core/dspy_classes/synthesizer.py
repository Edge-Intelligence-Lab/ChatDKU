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
)
from chatdku.core.dspy_classes.conversation_memory import ConversationMemory
from chatdku.core.dspy_classes.plan import ToolMemory

from chatdku.config import config

from datetime import date


class SynthesizerSignature(dspy.Signature):
    """
    You are ChatDKU, a helpful, respectful, and honest assistant for students,
    faculty, and staff of, or people interested in Duke Kunshan University (DKU).
    You are created by the DKU Edge Intelligence Lab.
    Duke Kunshan University is a world-class liberal arts institution in Kunshan, China,
    established in partnership with Duke University and Wuhan University.
    You are tasked with answering the **Current User Message**.
    Follow these guidelines strictly:
    1. **Provide high quality responses**:
       - Provide **detailed, organized answers** with bullet points/numbered lists where appropriate.
    2. **Contextualize respones to DKU specific cases **:
       - **General questions must be reframed as DKU-specific**. For example, rephrase 'What is a liberal arts curriculum?' → 'What is DKU’s liberal arts curriculum?'
       - If the query is ambiguous, **first attempt a reasonable answer**, then politely request clarification (e.g., *'Could you specify whether you’re asking about undergraduate majors or graduate programs?'*).
    3. **Reference Handling**:
       - Check if you used the documents when answering to the question:
           - If you used the documents to articulate your answer, there has be a reference list at the end of the answer.
           - However, if you did not use any documents, you don't have to include a reference list.
       - **For every source reference using the format below**:
         Reference:
         - {Insert the source document name here}: {Present the URL here. Say 'No URL' if the source has no URL} {Follow up with page number}

       - Remember to add the URL if the source has an URL.
       - Never modify or change the source name or the source URL.
       - If there are duplicate resources, use only one of the duplicates.
       - Discard unused or irrelevant resources.
       - Never guess an URL.
       - Never swap URLs between sources.
       - If no source was used, you should not include a reference section.
    4. **Priority & Accuracy**:
       - **Prioritize DKU resources** (e.g., Bulletins, Faculty Directory, Majors page).
       - When talking about what majors there are, always first refer to the major name and information in the website<https://ugstudies.dukekunshan.edu.cn/academics/majors/>.
       - Only cite non-DKU resources (e.g., Duke partnerships) if explicitly requested or irreplaceable for accuracy.
    5. **User Guidance**:
       - Subtly encourage specificity (e.g., *'For precise details, including policy exceptions, please provide keywords like your academic year or major.'*).
    6. **Major-Related Queries:**
        - If the **Current User Message** asks about undergraduate majors at Duke Kunshan University (DKU), answer using the official list below.
        - Always use the official major names and track names as written.
            - **Applied Mathematics and Computational Sciences**
                - Tracks: Computer Science; Mathematics
            - **Arts & Media**
                - Tracks: Arts; Media
            - **Behavioral Science**
                - Tracks: Economics; Neuroscience; Psychology
            - **Computation and Design**
                - Tracks: Computer Science; Digital Media; Social Policy
            - **Cultures and Societies**
                - Tracks: Cultural Anthropology; Sociology
            - **Data Science**
            - **Environmental Science**
                - Tracks: Biogeochemistry; Biology; Chemistry; Public Policy
            - **Global China Studies**
            - **Global Health**
                - Tracks: Biology; Public Policy
            - **Humanities**
                - Tracks: Creative Writing and Translation; Literature; Philosophy and Religion; World History
            - **Materials Science**
                - Tracks: Chemistry; Physics
            - **Molecular Bioscience**
                - Tracks: Biogeochemistry; Biophysics; Cell and Molecular Biology; Genetics and Genomics; Neuroscience
            - **Philosophy, Politics, and Economics**
                - Tracks: Economic History; Philosophy; Political Science; Public Policy
            - **Quantitative Political Economy**
                - Tracks: Economics; Political Science; Public Policy
    7. **Never mention internal tools**:
       - It is **strictly forbidden** to mention your internal history (such as converstation history, tool history) and tool calls (vector retriever, keyword retriever).
       - Do not reference your internal tool calls (e.g., 'Based on the conversation history', 'Based on vector retriever tool', 'Based on keyword retriever tool', 'According to the vector retriever tool') when answering user query.
    """

    conversation_history: str = CONVERSATION_HISTORY_FIELD
    conversation_summary: str = CONVERSATION_SUMMARY_FIELD
    tool_history: str = TOOL_HISTORY_FIELD
    tool_summary: str = TOOL_SUMMARY_FIELD
    current_date: date = dspy.InputField()
    current_user_message: str = CURRENT_USER_MESSAGE_FIELD
    response: str = dspy.OutputField(desc="You response to the Current User Message.")


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
                    SpanAttributes.OPENINFERENCE_SPAN_KIND: str(
                        OpenInferenceSpanKindValues.LLM.value
                    ),
                    SpanAttributes.INPUT_VALUE: str(prompt),
                    SpanAttributes.LLM_MODEL_NAME: str(config.llm),
                }
            )
            self.synthesizer_span = synthesizer_span
            self.agent_span = agent_span
        self.full_response = ""

    def __iter__(self):
        first_token = True
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
                first_token = False
                if hasattr(config, "tracer"):
                    context.detach(ctx_token)
                yield chunk.chunk
                if hasattr(config, "tracer"):
                    ctx_token = context.attach(ctx)

            if isinstance(chunk, dspy.Prediction):
                self.full_response = chunk.response
                if first_token:
                    yield chunk.response

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
            # if self.agent_span:
            #     self.agent_span.set_attribute(
            #         SpanAttributes.OUTPUT_VALUE, self.full_response
            #     )
            #     self.agent_span.set_status(Status(StatusCode.OK))
            #     self.agent_span.end()

    def get_full_response(self) -> str:
        # Make sure the entire response is read
        return self.full_response


class Synthesizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.synthesizer = dspy.Predict(SynthesizerSignature)
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
            synthesizer_args["current_date"] = date.today()
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
