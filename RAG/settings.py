from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.llama_cpp import LlamaCPP
from argparse import ArgumentParser
from pathlib import Path
from typing import Callable, Union, Sequence, Optional
from llama_index.core.base.llms.types import ChatMessage

# FIXME: I have contributed these two functions to llama_index.llms.llama_cpp.llama_utils.
# Thus, the versions of them from LlamaIndex should be used whenever they were included
# in a stable release.
from llama_utils import (
    messages_to_prompt_v3_instruct,
    completion_to_prompt_v3_instruct,
    DEFAULT_SYSTEM_PROMPT,
)

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
    + """\
Do not begin your answer with phrases like "here is an answer"\
and respond with only the content of the answer.\
"""
)


def set_system_prompt(
    func: Callable[[Union[Sequence[ChatMessage], str], Optional[str]], str],
    system_prompt: str,
) -> Callable[[Union[Sequence[ChatMessage], str]], str]:
    def f(message: Union[Sequence[ChatMessage], str]) -> str:
        return func(message, system_prompt)

    return f


class Setting:
    data_dir="/opt/RAG_data"
    update=False


def parse_args_and_setup():
    parser = ArgumentParser()
    parser.add_argument("-e", "--embedding", type=str)
    parser.add_argument("-l", "--llm", type=Path)
    parser.add_argument("-u", "--update", action="store_true")
    parser.add_argument("-d", "--data_dir", type=Path)
    args = parser.parse_args()

    if args.data_dir is not None:
        Setting.data_dir = args.data_dir

    if args.update is not None:
        Setting.update = True

    # TODO: Use a better embedding model
    if args.embedding is None:
        embedding_name = "BAAI/bge-small-en-v1.5"
        print(f"Using default embedding {embedding_name}")
    else:
        embedding_name = args.embedding

    Settings.embed_model = HuggingFaceEmbedding(
        model_name=embedding_name, trust_remote_code=True
    )
    print("Loaded embedding model")

    if args.llm is None:
        Settings.llm = None
        print("Not using LLM")
    else:
        # NOTE: Arguments default to those that work with Llama3 8B, might consider adding
        # some arguments to change these values from CLI
        Settings.llm = LlamaCPP(
            model_path=str(args.llm),
            temperature=0.1,
            max_new_tokens=256,
            # Llama3 8B has a context window of 8192 tokens
            context_window=8192,
            # kwargs to pass to __call__()
            generate_kwargs={},
            # kwargs to pass to __init__()
            # set to at least 1 to use GPU
            model_kwargs={"n_gpu_layers": -1},
            # transform inputs into Llama format
            messages_to_prompt=set_system_prompt(
                messages_to_prompt_v3_instruct, COERCED_SYSTEM_PROMPT
            ),
            completion_to_prompt=set_system_prompt(
                completion_to_prompt_v3_instruct, COERCED_SYSTEM_PROMPT
            ),
            verbose=True,
        )
        print("Loaded LLM")

        # The same tokenizer as used by the LLM is used to count the number of tokens
        # accurately.
        Settings.tokenizer = Settings.llm._model.tokenizer()
        print("Loaded tokenizer")
