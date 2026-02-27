import dspy
import re
from urllib.parse import urlparse

from typing import Any

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
       - Before writing the final answer, perform this mandatory checklist for every retrieved item you actually used:
           1) Read both content and metadata.
           2) Extract these metadata fields when available: source name/title, URL/link, page/chunk locator, event identifier.
           3) Use metadata facts in the answer when relevant (especially event links and official URLs).
       - Metadata is a first-class source of truth and must be treated as equally important as body content.
       - If you used retrieved documents to answer, include a `Reference:` section at the end. If you used no retrieved documents, omit `Reference:`.
       - **Hard constraints (must follow):**
           - **If metadata has a URL/link, include that exact string in `Reference:`.**
           - **If metadata has no URL/link, write `No URL`.**
           - **Do not invent, normalize, complete, rewrite, or guess URLs.**
           - **Do not swap URLs across sources.**
           - **Do not modify source names; preserve them exactly as provided.**
           - **If an event is mentioned in the answer and its metadata has a URL, include that event URL in `Reference:`.**
           - **Remove duplicate references (same source + same URL).**
           - **Exclude unused references.**
             - You are given `metadata_reference_candidates`, which is built deterministically from retrieved metadata before generation.
                 - Treat it as the canonical source-url mapping.
                 - Do not alter URLs or source names from that mapping.
                 - If you use retrieved sources, keep your `Reference:` section consistent with this mapping.
       - Reference format (one bullet per used source):
         Reference:
         - {Exact source name}: {Exact metadata URL or `No URL`} {Page if available}
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
    # event_update test
    metadata_reference_candidates: str = dspy.InputField(
        desc=(
            "Deterministically extracted reference candidates from metadata. "
            "Use exact source names and URLs from here when building references."
        )
    )
    current_date: date = dspy.InputField()
    current_user_message: str = CURRENT_USER_MESSAGE_FIELD
    response: str = dspy.OutputField(desc="You response to the Current User Message.")


class ResponseGen:
    """A generator that uses the DSPY streamify."""

    # event_update test
    def __init__(
        self,
        prompt: str,
        streamer,
        enforced_reference_section: str = "",
        synthesizer_span: Span = None,
        agent_span: Span = None,
    ):
        self.llm_completion_gen = streamer
        self.enforced_reference_section = enforced_reference_section
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

    # event_update test
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

        if self.enforced_reference_section:
            reference_heading_present = re.search(
                r"(^|\n)\s*Reference\s*:\s*", self.full_response, flags=re.IGNORECASE
            )
            if reference_heading_present is None:
                addition = f"\n\n{self.enforced_reference_section}"
                self.full_response += addition
                yield addition
            else:
                missing_lines = [
                    line
                    for line in self.enforced_reference_section.splitlines()[1:]
                    if line.strip() and line not in self.full_response
                ]
                if missing_lines:
                    addition = "\n" + "\n".join(missing_lines)
                    self.full_response += addition
                    yield addition

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


def _recursive_find_metadata(value: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if isinstance(value, dict):
        metadata = value.get("metadata")
        if isinstance(metadata, dict):
            results.append(metadata)
        for child in value.values():
            results.extend(_recursive_find_metadata(child))
    elif isinstance(value, list):
        for child in value:
            results.extend(_recursive_find_metadata(child))
    return results


def _metadata_source_name(metadata: dict[str, Any]) -> str:
    source_keys = [
        "source",
        "source_name",
        "title",
        "document_title",
        "doc_name",
        "filename",
        "file_name",
        "event_name",
        "name",
        "file_path",
    ]
    for key in source_keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Unknown Source"


def _metadata_url(metadata: dict[str, Any]) -> str:
    url_keys = [
        "url",
        "URL",
        "link",
        "event_url",
        "source_url",
        "web_url",
    ]
    for key in url_keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            normalized_value = value.strip()
            if normalized_value.lower() in {"no url", "none", "n/a", "na"}:
                return "No URL"
            return normalized_value
    return "No URL"


def _metadata_locator(metadata: dict[str, Any]) -> str:
    locator_keys = [
        "page_label",
        "page_number",
        "page",
        "chunk_id",
        "chunk_index",
        "start_page",
        "end_page",
    ]
    for key in locator_keys:
        value = metadata.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return f"(page: {value})"
    return ""


def _normalize_source_name(source: str, url: str) -> str:
    if source.lower() in {"index.html", "index.htm"} and url != "No URL":
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.strip()
        path_parts = [part for part in parsed_url.path.split("/") if part]
        if path_parts:
            page_name = path_parts[-1]
            return f"{page_name} ({domain})" if domain else page_name
        if domain:
            return domain
    return source


def _build_metadata_reference_candidates(tool_memory: ToolMemory) -> list[str]:
    references: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    for entry in tool_memory.history:
        metadata_list = _recursive_find_metadata(entry.result)
        for metadata in metadata_list:
            source = _metadata_source_name(metadata)
            url = _metadata_url(metadata)
            source = _normalize_source_name(source, url)
            locator = _metadata_locator(metadata)
            key = (source, url, locator)
            if key in seen:
                continue
            seen.add(key)
            locator_suffix = f" {locator}" if locator else ""
            references.append(f"- {source}: {url}{locator_suffix}")

    return references


def _build_reference_section(tool_memory: ToolMemory) -> str:
    candidates = _build_metadata_reference_candidates(tool_memory)
    if not candidates:
        return ""
    return "Reference:\n" + "\n".join(candidates)


def _replace_reference_section(response: str, reference_section: str) -> str:
    if not reference_section:
        return response

    marker = re.search(r"(^|\n)\s*Reference\s*:\s*", response, flags=re.IGNORECASE)
    stripped_response = response.strip()
    if marker:
        prefix = response[: marker.start()].rstrip()
        if prefix:
            return f"{prefix}\n\n{reference_section}"
        return reference_section

    if stripped_response:
        return f"{stripped_response}\n\n{reference_section}"
    return reference_section


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
            "metadata_reference_candidates": 2 / 15,
        }

    def get_token_limits(self) -> dict[str, int]:
        return token_limit_ratio_to_count(
            self.token_ratios, len(get_template(self.synthesizer))
        )

    # event_update test
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
            reference_section = _build_reference_section(tool_memory)
            synthesizer_args = dict(
                current_user_message=current_user_message,
                conversation_history=conversation_memory.history_str(),
                conversation_summary=conversation_memory.summary,
                # TODO: Might want to unify conversion to string for `ToolMemory`
                tool_history="\n\n###\n\n".join(
                    [i.model_dump_json() for i in tool_memory.history]
                ),
                tool_summary=tool_memory.summary,
                metadata_reference_candidates=(
                    reference_section if reference_section else "No metadata references"
                ),
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
                        reference_section,
                        span,
                        parent_span if final else None,
                    )

                else:
                    response_gen = ResponseGen(
                        synthesizer_template,
                        synthesizer_streamer(**synthesizer_args),
                        reference_section,
                    )
                return dspy.Prediction(response=response_gen)

        else:
            with (
                use_span(span, end_on_exit=True)
                if hasattr(config, "tracer")
                else nullcontext()
            ):
                response = self.synthesizer(**synthesizer_args).response
                response = _replace_reference_section(response, reference_section)
                span.set_attribute(SpanAttributes.OUTPUT_VALUE, response)
                span.set_status(Status(StatusCode.OK))
                return dspy.Prediction(response=response)
