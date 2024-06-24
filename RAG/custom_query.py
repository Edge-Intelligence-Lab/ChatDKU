"""Pipeline schema."""

from typing import Any, Generator, List, Union, cast, get_args


from llama_index.core.base.llms.types import (
    ChatResponse,
    CompletionResponse,
    ChatMessage,
)
from llama_index.core.base.response.schema import Response
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

# Define common types used throughout these components
StringableInput = Union[
    CompletionResponse,
    ChatResponse,
    str,
    QueryBundle,
    Response,
    Generator,
    NodeWithScore,
    TextNode,
]


def validate_and_convert_stringable(input: Any) -> str:
    # special handling for generator
    if isinstance(input, Generator):
        # iterate through each element, make sure is stringable
        new_input = ""
        for elem in input:
            if not isinstance(elem, get_args(StringableInput)):
                raise ValueError(f"Input {elem} is not stringable.")
            elif isinstance(elem, (ChatResponse, CompletionResponse)):
                new_input += cast(str, elem.delta)
            else:
                new_input += str(elem)
        return new_input
    elif isinstance(input, List):
        # iterate through each element, make sure is stringable
        # do this recursively
        new_input_list = []
        for elem in input:
            new_input_list.append(validate_and_convert_stringable(elem))
        return str(new_input_list)
    elif isinstance(input, ChatResponse):
        return input.message.content or ""
    elif isinstance(input, ChatMessage):
        return input.content or ""
    elif isinstance(input, get_args(StringableInput)):
        return str(input)
    else:
        raise ValueError(f"Input {input} is not stringable; its type is {type(input)}.")
