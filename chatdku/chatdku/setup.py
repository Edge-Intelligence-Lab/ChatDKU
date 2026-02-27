import os

import transformers
from llama_index.core import Settings
from llama_index.embeddings.text_embeddings_inference import TextEmbeddingsInference
from phoenix.otel import register
from transformers import AutoTokenizer

from chatdku.config import config


def mydeepcopy(self, memo):
    return self


def setup(add_system_prompt: bool = False, use_llm: bool = True) -> None:
    """Setup common resources from command line arguments."""
    # A Text Embeddings Inference server is used to serve the embedding model
    # The endpoint should be of the format [base_url]/[author]/[model_name]
    Settings.embed_model = TextEmbeddingsInference(
        model_name=config.embedding,
        base_url=config.tei_url + "/" + config.embedding,
    )
    print(f"Using embedding model {config.embedding}")

    # Suppress warning
    # "Special tokens have been added in the vocabulary,
    # make sure the associated word embeddings are fine-tuned or trained."
    transformers.logging.set_verbosity_error()

    # The same tokenizer as used by the LLM is used to count the number of tokens
    # accurately.
    Settings.tokenizer = AutoTokenizer.from_pretrained(config.tokenizer)
    print("Loaded tokenizer")


def use_phoenix():
    phoenix_host = os.environ.get("PHOENIX_HOST", "127.0.0.1")
    phoenix_port = os.environ.get("PHOENIX_PORT", 6007)
    collector_endpoint = f"http://{phoenix_host}:{phoenix_port}/v1/traces"
    tracer_provider = register(
        project_name="ChatDKU_student_release",  # Default is 'default'
        auto_instrument=True,  # See 'Trace all calls made to a library' below
        endpoint=collector_endpoint,
        batch=True,
    )
    config.tracer = tracer_provider.get_tracer(__name__)
