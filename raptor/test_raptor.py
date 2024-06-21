from raptor import (
    BaseSummarizationModel,
    BaseQAModel,
    BaseEmbeddingModel,
    RetrievalAugmentationConfig,
    RetrievalAugmentation,
)
from sentence_transformers import SentenceTransformer
from llama_cpp import Llama


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


llm = Llama(model_path="/opt/llm/Meta-Llama-3-8B-Instruct-q8_0.gguf", n_gpu_layers=-1, n_ctx=8192)

RAC = RetrievalAugmentationConfig(
    summarization_model=LlamaSummarizationModel(llm),
    qa_model=LlamaQAModel(llm),
    embedding_model=BgeEmbeddingModel(),
    tb_max_tokens=1024,
)
RA = RetrievalAugmentation(config=RAC)

with open("demo/sample.txt", "r") as file:
    text = file.read()
RA.add_documents(text)

question = "How did Cinderella reach her happy ending?"

answer = RA.answer_question(question=question, max_tokens=7000)

print("Answer: ", answer)
