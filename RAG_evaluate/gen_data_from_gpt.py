from openai import OpenAI
import json

client = OpenAI(
    api_key="sk-proj-lXR90jxYtuD7lQWmpPSfT3BlbkFJl1hbYFXxtYPYvMwwUxQe",
)

def get_chat_messages(prompt_text):
    response = client.chat.completions.create(
        model="gpt-4o",  
        messages=prompt_text,
        max_tokens=3000,
        n=1,
        stop=None,
        temperature=0.5,
    )
    return response.choices[0].message.content


# expected output format
output_format='{ \
    "abstract":"", \
    "triple1":{ \
        "question":"", \
        "contexts":"", \
        "answer":"", \
    }, \
    ...., \
    "triple10":{ \
        "question":"", \
        "contexts":"", \
        "answer":"", \
    } \
}'

# Delete some of the extra stuff when gpt generates output
def remove_backslashes_and_newlines(input_string):
    # remove \
    result = input_string.replace("\\", "")
    # remove \n
    result = result.replace('\n', '')
    result = result.replace('```json', '')
    result = result.replace('```', '')
    return result



def main():
    # load Load the preprocessed doucments
    with open('./documents/documents_for_gen.json', 'r', encoding='utf-8') as file:
        documents = json.load(file)
    gpt_gen = []

    # generate output from GPT 4o
    num = 0
    for document in documents:
        print(f"{num}/173")
        num += 1
        text = document["content"]
        prompt_text = [{"role": "system", "content": "You are an expert at summarizing text, and are good at summarizing, asking and answering questions about text."},
            {"role":"user","content":"The input you will be given will be a long text. You should summarize this text, and give the following output: 1.abstract(‘What does this passage say about it, and what problems can it solve’) 2.question-context-answer tuple(Ask a question about the text, give the context related to the question, and then give the answer to the question)(Ten triples need to be given).Please give the output in the required format as follow:{output_format}".format(output_format=output_format)},
            {"role": "assistant", "content": "Ok, I will summarize the file according to the format you gave. Please send me the text"},
            {"role": "user", "content": "Here is the text:[{text}],Please give the output in the required format".format(text=text)},
                    ]
        response_content = get_chat_messages(prompt_text)
        gpt_gen.append(response_content)

    # transform string(from GPT) to json
    num = -1
    new_gpt_gen = []
    for item in gpt_gen:
        num += 1
        new_item = remove_backslashes_and_newlines(item)
        try:
            json_object = json.loads(new_item)
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: {e}")
            print(num)
        new_gpt_gen.append(json_object)
    for i in range(0,len(documents)):
        new_gpt_gen[i]['document_id'] = documents[i]['document_id']
        new_gpt_gen[i]['file_path'] = documents[i]['file_path']
    raw_datas = new_gpt_gen
    pre_dataset = []
    for data in raw_datas:
        for index in range(1,11):
            tmp_dic = {}
            tmp_dic["document_id"] = data["document_id"]
            tmp_dic["file_path"] = data["file_path"]
            tmp_dic["abstract"] = data["abstract"]
            tmp_dic["question"] = data[f"triple{index}"]["question"]
            tmp_dic["ground_truth_contexts"] = data[f"triple{index}"]["contexts"]
            tmp_dic["ground_truth"] = data[f"triple{index}"]["answer"]
            pre_dataset.append(tmp_dic)

    file_path = "../data_for_rag/before_RAG_dataset.json"
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(pre_dataset, json_file, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()