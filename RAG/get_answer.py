from query import get_pipeline
from settings import parse_args_and_setup
from llama_index.core.response_synthesizers import ResponseMode
import json


def main():
    file_path = "../RAG_evaluate/data_for_rag/before_RAG_dataset.json"
    with open(file_path, 'r', encoding='utf-8') as file:
        json_datas = json.load(file)
    json_questions = []
    for json_data in json_datas:
        json_questions.append(json_data['question'])

    parse_args_and_setup()

    pipeline = get_pipeline(
        retriever_type="fusion",
        hyde=True,
        vector_top_k=10,
        bm25_top_k=10,
        fusion_top_k=10,
        num_queries=3,
        synthesize_response=True,
        response_mode=ResponseMode.COMPACT,
    )
    print("-"*50)
    print("pipeline prepared")


    print("-"*50)
    print("Strating RAG")
    # output = pipeline.run(input="Where can the electronic version of the DKU Student Handbook be found?")
    # print(output)
    num = 0
    for json_question in json_questions:
        print(f"the {num} question")
        output = pipeline.run(input=json_question)
        print(output)
        json_datas[num]["answer"] = output.response_txt
        context = []
        try:
            for i in range(0,5):
                context.append([output.source_nodes[i].node.text])
        except:
            json_datas[num]["context_error"] = True
        json_datas[num]["contexts"] = context
        num += 1

    save_file_path = "../RAG_evaluate/data_for_ragas/fusion_hyde_true_eng_top10.json"
    with open(save_file_path, 'w', encoding='utf-8') as file:
        json.dump(json_datas, file, indent=2, ensure_ascii=False)



if __name__ == "__main__":
    main()