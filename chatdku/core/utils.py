import re
from inspect import Signature, signature
from typing import Any, Callable, Optional

from llama_index.core import Settings
from llama_index.core.node_parser import TokenTextSplitter
from openinference.instrumentation import safe_json_dumps
from openinference.semconv.trace import OpenInferenceMimeTypeValues, SpanAttributes
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic.fields import FieldInfo

from chatdku.config import config


def span_add_inputs(span, **kwargs):
    span.set_attributes(
        {
            SpanAttributes.INPUT_VALUE: safe_json_dumps(kwargs),
            SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
        }
    )


def span_add_outputs(span, **kwargs):
    span.set_attributes(
        {
            SpanAttributes.INPUT_VALUE: safe_json_dumps(kwargs),
            SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
        }
    )


def span_start(span_name: str, span_kind, **kwargs):
    """Start a OTLP span.

    Args:
        span_name (str): Name of the span to start.
        span_kind (openinference.semconv.trace.OpenInferenceSpanKindValues).
        current (bool): Whether to use start_as_a_current_span or not.
            Will use start_span otherwise.
        kwargs: Add your inputs in {keyword=value} format here.


    Returns:
        OTLP span
    """
    span = config.tracer.start_span(span_name)
    span.set_attribute(
        SpanAttributes.OPENINFERENCE_SPAN_KIND,
        span_kind.value,
    )
    if kwargs:
        span.set_attributes(
            {
                SpanAttributes.INPUT_VALUE: safe_json_dumps(kwargs),
                SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
            }
        )
    return span


def span_ctx_start(span_name: str, span_kind, parent_context=None):
    return config.tracer.start_as_current_span(
        span_name,
        attributes={SpanAttributes.OPENINFERENCE_SPAN_KIND: span_kind.value},
        context=parent_context,
    )


class NameParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    params: Any


def func_to_model(
    name: str, func: Callable[..., Any], exclude: list[str] = []
) -> type[BaseModel]:
    fields = {}
    params = signature(func).parameters

    for param_name in params:
        if param_name in exclude:
            continue

        param_type = params[param_name].annotation
        if param_type is Signature.empty:
            param_type = Any

        param_default = params[param_name].default
        if param_default is Signature.empty:
            fields[param_name] = (param_type, Field(...))
        elif isinstance(param_default, FieldInfo):
            fields[param_name] = (param_type, param_default)
        else:
            fields[param_name] = (param_type, Field(default=param_default))

    return create_model(name, **fields)


def camel_to_snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def strs_fit_max_tokens_reverse(
    strs: list[str], concat_str: str, max_tokens: int
) -> int:
    """Returns the minimum index `i` such that `strs[i:]` concatenated could fit `max_tokens`.
    The list of strings would be tokenized and reversed, then concatenate one by one,
    assuming that `concat_str` would be added between two strings from the list.

    Args:
        `strs`: A list of strings.
        `concat_str`: The string that would be used to concatenate the strings.
        `max_tokens`: The maximum number of tokens to fit in.
    """

    str_lens = [len(Settings.tokenizer(i)) for i in strs]
    concat_len = len(Settings.tokenizer(concat_str))
    min_index = len(str_lens) - 1
    cum_sum = 0
    for i in reversed(range(len(str_lens))):
        cum_sum += str_lens[i]
        if i > 0:
            cum_sum += concat_len
        if cum_sum > max_tokens:
            break
        min_index = i

    return min_index


def truncate_tokens(
    s: str, max_tokens: int, tokenizer: Optional[Callable] = None
) -> str:
    """Truncate string so that it does not exceed the given number of tokens."""

    splitter = TokenTextSplitter(
        chunk_size=int(abs(max_tokens)), chunk_overlap=0, tokenizer=tokenizer
    )
    return splitter.split_text(s)[0]


def truncate_tokens_all(
    s: dict[str, str], max_tokens: dict[str, int], tokenizer: Optional[Callable] = None
) -> dict[str, str]:
    return {k: truncate_tokens(v, max_tokens[k], tokenizer) for k, v in s.items()}


def token_limit_ratio_to_count(
    ratios: dict[str, float], template_length: int, reserved: int = 100
) -> dict[str, int]:
    """Convert token limit ratio of the fields to the max number of tokens.
    Each field is limited to have a max length of
    (context_window - prompt_length) * ratio

    Args:
        ratios: The proportion of tokens to give to each field.
        template_length: Length of the prompt template.
        reserved: The amount of token reserved in case there were some special tokens.
    """
    remain = config.context_window - template_length - reserved
    return {k: int(v * remain) for k, v in ratios.items()}


def load_conversation(history: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    convert (role,content) to (content_bot,content_bot) from past conversation.
    This method is applicable only for backend.

    Args:
        history: List on tuple containing role and content.

    """

    past_messages = []

    for user_msg, bot_msg in zip(history, history[1:]):
        if str(user_msg[0]).lower() == "user" and str(bot_msg[0]).lower() == "bot":
            user_message = user_msg[1]
            bot_message = bot_msg[1]
            past_messages.append(tuple([user_message, bot_message]))
    return past_messages


# From the DSPY.react code
# https://github.com/stanfordnlp/dspy/blob/bb110a0262f2373150d864792bcc92e76f43cd62/dspy/predict/react.py#L91-L94
def format_trajectory(trajectory: dict[str, Any]):
    adapter = dspy.settings.adapter or dspy.ChatAdapter()
    trajectory_signature = dspy.Signature(f"{', '.join(trajectory.keys())} -> x")
    return adapter.format_user_message_content(trajectory_signature, trajectory)
