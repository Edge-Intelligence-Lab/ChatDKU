from datasets import Dataset 
import os
import json
from ragas import evaluate
from ragas.metrics import faithfulness, answer_correctness
from itertools import chain
from typing import List, Sequence
from langchain_openai.chat_models import ChatOpenAI


os.environ["OPENAI_API_KEY"] = "api-key-here"

def main():
    # load json file
    file_path = "./data_for_ragas/ragas_dataset.json"
    with open(file_path, 'r', encoding='utf-8') as file:
        json_datas = json.load(file)
    for i in range(len(json_datas)):
        json_datas[i]["contexts"] = list(chain(*json_datas[i]["contexts"]))
    dataset = Dataset.from_list(json_datas)

    gpt4 = ChatOpenAI(model_name="gpt-4o")

    result = evaluate(
        dataset.select(range(10)),  # showing only 10 for demonstration
        metrics=[faithfulness, answer_correctness],
        llm=gpt4,
    )

    print(result)



if __name__ == "__main__":
    main()