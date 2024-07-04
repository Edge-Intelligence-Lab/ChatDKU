from llama_index.core import Settings
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.llama_cpp.llama_utils import (
    messages_to_prompt_v3_instruct,
    completion_to_prompt_v3_instruct,
    DEFAULT_SYSTEM_PROMPT,
)
from llama_index.core.base.llms.types import ChatMessage
import transformers
from transformers import AutoTokenizer
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable, Union, Sequence, Optional

import llama_index


def mydeepcopy(self, memo):
    return self


# FIXME: Ugly hack for the issue that DSPy's use of `deepcopy()` cannot copy
# certain attributes (probably due to the being Pydantic `PrivateAttr()`?)
llama_index.llms.openai_like.OpenAILike.__deepcopy__ = mydeepcopy

# When executing tasks like summarizing, the LLM is supposed to ONLY generate the
# summaries themselves. However, the LLM sometimes says things like
# `here is a summary of the given text` before the summary. This prompt used to
# explicitly discourage this kind of output.
#
# Also note that I have tried other things like `do not begin your answer with
# "here are the generated queries"` to discourage such messages at the beginning of
# the generated queries. Nevertheless, this prompt seems to be the most effective.
COERCED_SYSTEM_PROMPT = (
    DEFAULT_SYSTEM_PROMPT
    + 'Do not begin your answer with phrases like "here is an answer" '
    "and respond with only the content of the answer."
)


class UseCoercedPrompt:
    def __init__(
        self,
        func: Union[
            Callable[[Sequence[ChatMessage], Optional[str]], str],
            Callable[[str, Optional[str]], str],
        ],
    ):
        self.func = func

    def __call__(self, message: Union[Sequence[ChatMessage], str]) -> str:
        return self.func(message, COERCED_SYSTEM_PROMPT)


class Config:
    vector_store_path: str
    docstore_path: str


def get_parser() -> ArgumentParser:
    """
    Get the parent parser for the common arguments between different scripts.

    The common arguments should use uppercase letters for their short forms,
    while the script-specific arguments should use lowercase letters for the
    short forms.
    """
    parser = ArgumentParser(add_help=False)
    parser.add_argument("-E", "--embedding", type=str, default="BAAI/bge-small-en-v1.5")
    parser.add_argument(
        "-L",
        "--llm",
        type=str,
        default="meta-llama/Meta-Llama-3-8B-Instruct",
    )
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434")
    parser.add_argument("--llm-url", type=str, default="http://localhost:8000/v1")
    parser.add_argument(
        "-V",
        "--vector-store",
        type=Path,
        default=Path("./chroma_db"),
    )
    parser.add_argument(
        "-D",
        "--docstore",
        type=Path,
        default=Path("./docstore"),
    )
    return parser


def setup(args: Namespace) -> None:
    """Setup common resources from command line arguments."""

    # An Ollama server is used to serve the embedding model
    Settings.embed_model = OllamaEmbedding(
        model_name=args.embedding,
        base_url=args.ollama_url,
    )
    print(f"Loaded embedding model {args.embedding}")

    # Suppress warning
    # "Special tokens have been added in the vocabulary, make sure the associated word embeddings are fine-tuned or trained."
    transformers.logging.set_verbosity_error()

    # The same tokenizer as used by the LLM is used to count the number of tokens
    # accurately.
    Settings.tokenzier = AutoTokenizer.from_pretrained(args.llm)
    print("Loaded tokenizer")

    # An OpenAI-like API endpoint is needed for the LLM, which could be hosted
    # with e.g. vLLM
    Settings.llm = OpenAILike(
        model=args.llm,
        api_base=args.llm_url,
        api_key="fake",  # A dummy API key is needed or else connection error would occur
        context_window=8192,
        temperature=0.7,
        is_chat_model=False,  # Set to False to use custom messages/completion_to_prompt() functions
        is_function_calling_model=False,
        tokenizer=args.llm,  # Use a tokenizer to enable token counting (just pass the name of the LLM is OK)
        messages_to_prompt=UseCoercedPrompt(messages_to_prompt_v3_instruct),
        completion_to_prompt=UseCoercedPrompt(completion_to_prompt_v3_instruct),
    )
    print("Loaded LLM")

    Config.vector_store_path = str(args.vector_store)
    Config.docstore_path = str(args.docstore)
