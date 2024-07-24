from llama_index.core import Settings
from llama_index.embeddings.text_embeddings_inference import TextEmbeddingsInference
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.base.llms.types import ChatMessage
import transformers
from transformers import AutoTokenizer
from typing import Callable, Union, Sequence, Optional

import llama_index


def mydeepcopy(self, memo):
    return self


# FIXME: Ugly hack for the issue that DSPy's use of `deepcopy()` cannot copy
# certain attributes (probably due to the being Pydantic `PrivateAttr()`?)
llama_index.llms.openai_like.OpenAILike.__deepcopy__ = mydeepcopy

import os
import phoenix as px
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


class Config:
    def __init__(self, embedding_model_type="small"):

        # about settings.py
        self.embedding = f"BAAI/bge-m3"
        self.llm = "meta-llama/Meta-Llama-3-8B-Instruct"
        self.tokenizer = "/opt/tokenizer/Meta-Llama-3-8B-Instruct"
        self.tei_url = "http://localhost:18080"
        self.llm_url = "http://localhost:8000/v1"

        # about load_and_index
        self.data_dir = "/opt/RAG_data"
        self.documents_path = "/opt/RAG_data/new_parser_documents.pkl"
        self.pipeline_cache = "./pipeline_cache"
        self.update = False

        # about query
        self.chroma_db = f"/opt/chroma_dbs/bge_m3_chroma_db"
        # self.nodes_path = f"./nodes/nodes_{str(embedding_model_type)}_bge.pkl"
        self.docstore_path = f"/opt/docstores/bge_m3_docstore"


def completion_to_prompt(completion: str, system_prompt: Optional[str] = None) -> str:
    """
    Convert completion instruction string to Llama 3 Instruct format with no system prompt.

    System prompt is not used because it is difficult to specify a different one
    on each call, which makes it difficult to count the number of tokens.

    Reference: https://llama.meta.com/docs/model-cards-and-prompt-formats/meta-llama-3/

    Note: `<|begin_of_text|>` is not needed as Llama.cpp appears to add it already.
    """
    return (
        f"<|start_header_id|>user<|end_header_id|>\n\n"
        f"{completion.strip()}<|eot_id|>\n"
        f"<|start_header_id|>assistant<|end_header_id|>\n\n"
    )


def setup() -> None:
    """Setup common resources from command line arguments."""
    config = Config()

    # A Text Embeddings Inference server is used to serve the embedding model
    # The endpoint should be of the format [base_url]/[author]/[model_name]
    Settings.embed_model = TextEmbeddingsInference(
        model_name=config.embedding,
        base_url=config.tei_url + "/" + config.embedding,
    )
    print(f"Using embedding model {config.embedding}")

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
        completion_to_prompt=completion_to_prompt,
    )
    print("Using LLM")


def use_phoenix():
    # NOTE: I cannot find how to disable gRPC for Phoenix, so I would just
    # pass in port 0 to make it easier to avoid port collision.
    os.environ["PHOENIX_GRPC_PORT"] = "0"
    px.launch_app()
    phoenix_port = os.environ.get("PHOENIX_PORT", 6006)
    endpoint = f"http://127.0.0.1:{phoenix_port}/v1/traces"
    tracer_provider = trace_sdk.TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint)))
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
