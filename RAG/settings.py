from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.llama_cpp import LlamaCPP
from llama_index.llms.llama_cpp.llama_utils import DEFAULT_SYSTEM_PROMPT
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional


# NOTE: Not using `completion_to_prompt()` supplied in llama_utils as Llama 3 uses
# a different prompt format.
#
# TODO: Also implement `messages_to_prompt()` for Llama 3. However, it is used for
# `llm.chat()` as opposed to `llm.complete()`, which is used only in a few places
# such as agents. So this might not be an urgent task. Also consider opening a PR
# to contribute back to LlamaIndex?
def completion_to_prompt(completion: str, system_prompt: Optional[str] = None) -> str:
    system_prompt_str = system_prompt or DEFAULT_SYSTEM_PROMPT

    return (
        f"<|start_header_id|>system<|end_header_id|>\n\n"
        f"{system_prompt_str.strip()}<|eot_id|>"
        f"<|start_header_id|>user<|end_header_id|>\n\n"
        f"{completion.strip()}<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>\n\n"
    )


def parse_args_and_setup():
    parser = ArgumentParser()
    parser.add_argument("-e", "--embedding", type=str)
    parser.add_argument("-l", "--llm", type=Path)
    args = parser.parse_args()

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
            model_kwargs={"n_gpu_layers": 1},
            # transform inputs into Llama format
            messages_to_prompt=None,
            completion_to_prompt=completion_to_prompt,
            verbose=True,
        )
        print("Loaded LLM")

        # The same tokenizer as used by the LLM is used to count the number of tokens
        # accurately.
        Settings.tokenizer = Settings.llm._model.tokenizer()
        print("Loaded tokenizer")
