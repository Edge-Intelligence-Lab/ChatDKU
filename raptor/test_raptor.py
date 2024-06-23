from raptor import (
    BaseSummarizationModel,
    BaseQAModel,
    BaseEmbeddingModel,
    RetrievalAugmentationConfig,
    RetrievalAugmentation,
)
from sentence_transformers import SentenceTransformer
from llama_cpp import Llama
from argparse import ArgumentParser
from pathlib import Path
from llama_index.core.schema import MetadataMode
import pickle


class LlamaSummarizationModel(BaseSummarizationModel):
    def __init__(self, llm):
        self._llm = llm

    def summarize(self, context, max_tokens=256):
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant who gives answers directly"
                "without saying things like `here is the answer`.",
            },
            {
                "role": "user",
                "content": f"Write a summary of the following, including as many key details as possible: {context}:",
            },
        ]
        output = llm.create_chat_completion(messages=messages, max_tokens=max_tokens)
        return output["choices"][0]["message"]["content"]


class LlamaQAModel(BaseQAModel):
    def __init__(self, llm):
        self._llm = llm

    def answer_question(self, context, question):
        messages = [
            {
                "role": "system",
                "content": f"Given Context: {context} Give the best full answer amongst the option to question {question}",
            },
            {
                "role": "user",
                "content": f"Write a summary of the following, including as many key details as possible: {context}:",
            },
        ]
        output = llm.create_chat_completion(messages=messages, max_tokens=None)
        return output["choices"][0]["message"]["content"]


class BgeEmbeddingModel(BaseEmbeddingModel):
    def __init__(self, model_name="BAAI/bge-small-en-v1.5"):
        self.model = SentenceTransformer(model_name)

    def create_embedding(self, text):
        return self.model.encode(text)


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "-l",
        "--llm",
        type=Path,
        default=Path("/opt/llm/Meta-Llama-3-8B-Instruct-q8_0.gguf"),
    )
    parser.add_argument(
        "-d", "--data-file", type=Path, default=Path("/opt/RAG_data/documents.pkl")
    )
    args = parser.parse_args()

    with open(args.data_file, "rb") as file:
        documents = pickle.load(file)
    text = "\n".join(
        [doc.get_content(metadata_mode=MetadataMode.LLM) for doc in documents]
    )

    llm = Llama(
        model_path=str(args.llm),
        n_gpu_layers=-1,
        n_ctx=8192,
    )
    RAC = RetrievalAugmentationConfig(
        summarization_model=LlamaSummarizationModel(llm),
        qa_model=LlamaQAModel(llm),
        embedding_model=BgeEmbeddingModel(),
        tb_max_tokens=1024,
    )
    RA = RetrievalAugmentation(config=RAC)
    RA.add_documents(text)

    while True:
        try:
            print("*" * 32)
            question = input("> ")
            answer = RA.answer_question(question=question, max_tokens=7000)
            print("+" * 32)
            print(answer)
        except EOFError:
            break


if __name__ == "__main__":
    main()
