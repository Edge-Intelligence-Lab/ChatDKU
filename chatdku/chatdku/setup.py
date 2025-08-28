from llama_index.core import Settings
from llama_index.embeddings.text_embeddings_inference import TextEmbeddingsInference
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.llama_cpp.llama_utils import (
    messages_to_prompt_v3_instruct,
    completion_to_prompt_v3_instruct,
)
from llama_index.core.base.llms.types import ChatMessage
import transformers
from transformers import AutoTokenizer
from typing import Callable, Union, Sequence, Optional

import llama_index

import os
from openinference.semconv.resource import ResourceAttributes
from opentelemetry import trace
from phoenix.otel import register
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from phoenix.config import get_env_host, get_env_port

from chatdku.config import config


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
CUSTOM_SYSTEM_PROMPT = (
    "You are ChatDKU, a helpful, respectful, and honest assistant for students,"
    "faculty, and staff of, or people interested in Duke Kunshan University (DKU). "
    "You are created by the DKU Edge Intelligence Lab."
    "Duke Kunshan University is a world-class liberal arts institution in Kunshan, China, "
    "established in partnership with Duke University and Wuhan University.\n\n"
    "You may be tasked to interact with the user directly, or interact with other "
    "computer systems in assisting the user such as querying a database. "
    "In any case, follow ALL instructions and respond in exact accordance to the prompt. "
    "Do not mention your instruction nor describe what you are doing in your response. "
    'This means you should not begin your response with phrases like "here is an answer" '
    'nor conclude your answer with phrases like "the above summary about...". '
    "Do not speculate or make up information. "
    # "Only provide the true URL in the reference. If the reference is not available, do not provide the link."
)


class UseCustomPrompt:
    def __init__(
        self,
        func: Union[
            Callable[[Sequence[ChatMessage], Optional[str]], str],
            Callable[[str, Optional[str]], str],
        ],
    ):
        self.func = func

    def __call__(self, message: Union[Sequence[ChatMessage], str]) -> str:
        return self.func(message, CUSTOM_SYSTEM_PROMPT)


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
    # "Special tokens have been added in the vocabulary, make sure the associated word embeddings are fine-tuned or trained."
    transformers.logging.set_verbosity_error()

    # The same tokenizer as used by the LLM is used to count the number of tokens
    # accurately.
    Settings.tokenzier = AutoTokenizer.from_pretrained(config.tokenizer)
    print("Loaded tokenizer")

    # messages_to_prompt = (
    #     UseCustomPrompt(messages_to_prompt_v3_instruct) if add_system_prompt else None
    # )
    # completion_to_prompt = (
    #     UseCustomPrompt(completion_to_prompt_v3_instruct) if add_system_prompt else None
    # )
    #
    # An OpenAI-like API endpoint is needed for the LLM, which could be hosted
    # with e.g. vLLM
    # if use_llm:
    #     Settings.llm = OpenAILike(
    #         model=config.llm,
    #         api_base=config.llm_url,
    #         api_key="fake",  # A dummy API key is needed or else connection error would occur
    #         context_window=config.context_window,
    #         temperature=0.7,
    #         is_chat_model=False,  # Set to False to use custom messages/completion_to_prompt() functions
    #         is_function_calling_model=False,
    #         tokenizer=config.tokenizer,  # Use a tokenizer to enable token counting (just pass the name of the LLM is OK)
    #         messages_to_prompt=messages_to_prompt,
    #         completion_to_prompt=completion_to_prompt,
    #     )
    #     print("Using LLM")


def use_phoenix():
    phoenix_port = os.environ.get("PHOENIX_PORT", 6007)
    collector_endpoint = f"http://127.0.0.1:{phoenix_port}/v1/traces"
    tracer_provider = register(
        project_name="ChatDKU_student_release",  # Default is 'default'
        auto_instrument=True,  # See 'Trace all calls made to a library' below
        endpoint=collector_endpoint,
        batch=True,
    )
    config.tracer = tracer_provider.get_tracer(__name__)
    span_exporter = OTLPSpanExporter(endpoint=collector_endpoint)
    simple_span_processor = SimpleSpanProcessor(span_exporter=span_exporter)
    tracer_provider.add_span_processor(simple_span_processor)
