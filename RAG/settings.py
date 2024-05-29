from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.llama_cpp import LlamaCPP
from llama_index.llms.llama_cpp.llama_utils import (
    messages_to_prompt,
    completion_to_prompt,
)
from argparse import ArgumentParser
from pathlib import Path


def parse_args_and_setup():
    parser = ArgumentParser()
    parser.add_argument("-l", "--llm", type=Path, required=True)
    args = parser.parse_args()

    # TODO: Use a better embedding model
    Settings.embed_model = HuggingFaceEmbedding(
        model_name="BAAI/bge-small-en-v1.5", trust_remote_code=True
    )
    print("Loaded embedding model")

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
        messages_to_prompt=messages_to_prompt,
        completion_to_prompt=completion_to_prompt,
        verbose=True,
    )
    print("Loaded LLM")

    # The same tokenizer as used by the LLM is used to count the number of tokens
    # accurately.
    Settings.tokenizer = Settings.llm._model.tokenizer()
    print("Loaded tokenizer")
