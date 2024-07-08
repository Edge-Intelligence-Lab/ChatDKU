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
from config import Config

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
    "Additionally, Please be as organized as possible and give the source of the data."
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


def setup() -> None:
    """Setup common resources from command line arguments."""
    config = Config()

    # An Ollama server is used to serve the embedding model
    Settings.embed_model = OllamaEmbedding(
        model_name=config.embedding,
        base_url=config.ollama_url,
    )
    print(f"Loaded embedding model {config.embedding}")

    # Suppress warning
    # "Special tokens have been added in the vocabulary, make sure the associated word embeddings are fine-tuned or trained."
    transformers.logging.set_verbosity_error()

    # The same tokenizer as used by the LLM is used to count the number of tokens
    # accurately.
    Settings.tokenzier = AutoTokenizer.from_pretrained(config.llm)
    print("Loaded tokenizer")

    # An OpenAI-like API endpoint is needed for the LLM, which could be hosted
    # with e.g. vLLM
    Settings.llm = OpenAILike(
        model=config.llm,
        api_base=config.llm_url,
        api_key="fake",  # A dummy API key is needed or else connection error would occur
        context_window=8192,
        temperature=0.7,
        is_chat_model=False,  # Set to False to use custom messages/completion_to_prompt() functions
        is_function_calling_model=False,
        tokenizer=config.llm,  # Use a tokenizer to enable token counting (just pass the name of the LLM is OK)
        messages_to_prompt=UseCoercedPrompt(messages_to_prompt_v3_instruct),
        completion_to_prompt=UseCoercedPrompt(completion_to_prompt_v3_instruct),
    )
    print("Loaded LLM")
