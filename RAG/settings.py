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


def mydeepcopy(self, memo):
    return self


# FIXME: Ugly hack for the issue that DSPy's use of `deepcopy()` cannot copy
# certain attributes (probably due to the being Pydantic `PrivateAttr()`?)
llama_index.llms.openai_like.OpenAILike.__deepcopy__ = mydeepcopy

import os
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from phoenix.otel import register

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


class Config:
    def __init__(self, embedding_model_type="small"):

        # about settings.py
        self.embedding = f"BAAI/bge-m3"
        self.llm = "meta-llama/Meta-Llama-3.1-8B-Instruct"
        self.tokenizer = "/datapool/tokenizers/Meta-Llama-3.1-8B-Instruct"
        self.tokenizer = "/datapool/tokenizers/Meta-Llama-3.1-8B-Instruct"
        self.tei_url = "http://localhost:18080"
        self.llm_url = "http://localhost:8001/v1"
        self.context_window = 20000
        self.context_window = 20000

        # about load_and_index
        self.data_dir = "/datapool/RAG_data"
        self.documents_path = "/datapool/RAG_data/new_parser_documents.pkl"
        self.pipeline_cache = "./pipeline_cache"
        self.csv_path='/datapool/RAG_data_new_website/download_info.csv'#Store URL info of dku websites
        self.update = False

        # about query
        self.chroma_db = f"/datapool/chroma_dbs/bge_m3_chroma_db"
        # self.nodes_path = f"./nodes/nodes_{str(embedding_model_type)}_bge.pkl"
        self.docstore_path = f"/datapool/docstores/bge_m3_docstore"

        # about graphrag
        self.graph_data_dir = "/home/Glitterccc/projects/DKU_LLM/GraphDKU/output/20240715-182239/artifacts"
        self.graph_root_dir = "/home/Glitterccc/projects/DKU_LLM/GraphDKU"
        self.response_type = "Multiple Paragraphs"


def setup(add_system_prompt: bool = False) -> None:
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
    Settings.tokenzier = AutoTokenizer.from_pretrained(config.tokenizer)
    print("Loaded tokenizer")

    messages_to_prompt = (
        UseCustomPrompt(messages_to_prompt_v3_instruct) if add_system_prompt else None
    )
    completion_to_prompt = (
        UseCustomPrompt(completion_to_prompt_v3_instruct) if add_system_prompt else None
    )

    # An OpenAI-like API endpoint is needed for the LLM, which could be hosted
    # with e.g. vLLM
    Settings.llm = OpenAILike(
        model=config.llm,
        api_base=config.llm_url,
        api_key="fake",  # A dummy API key is needed or else connection error would occur
        context_window=config.context_window,
        temperature=0.7,
        is_chat_model=False,  # Set to False to use custom messages/completion_to_prompt() functions
        is_function_calling_model=False,
        tokenizer=config.tokenizer,  # Use a tokenizer to enable token counting (just pass the name of the LLM is OK)
        messages_to_prompt=messages_to_prompt,
        completion_to_prompt=completion_to_prompt,
    )
    print("Using LLM")


def use_phoenix():
    phoenix_port = os.environ.get("PHOENIX_PORT", 6007)
    tracer_provider = register(
        project_name="ChatDKU_main",
        endpoint=f"http://127.0.0.1:{phoenix_port}/v1/traces",
    )
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
