import re
from typing import Any, Callable
from pydantic import ConfigDict, BaseModel, Field, create_model
from pydantic.fields import FieldInfo
from inspect import signature, Signature
from llama_index.core import Settings


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
    min_index = len(str_lens)
    cum_sum = 0
    for i in reversed(range(len(str_lens))):
        cum_sum += str_lens[i]
        if i > 0:
            cum_sum += concat_len
        if cum_sum > max_tokens:
            break
        min_index = i

    return min_index
