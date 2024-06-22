import json
import pandas as pd
import tiktoken
import json
import re

def load_documents(file_path):
    with open(file_path, 'rb') as file:
        data = pd.read_pickle(file)
    return data

def count_tokens(text, model="gpt-4o"):
    encoder = tiktoken.encoding_for_model(model)
    tokens = encoder.encode(text)
    return len(tokens)

def contains_chinese(text):
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_pattern.search(text))

def main():
    documents_path = '../../RAG_data/documents.pkl'
    data = load_documents(documents_path)
    # load documents to List[Dict]
    documents = []
    for document in data:
        tmp_dic = {}
        tmp_dic["document_id"] = document.id_
        tmp_dic["file_path"] = document.metadata['file_path']
        tmp_dic["content"] = document.text
        tmp_dic["tokens"] = count_tokens(document.text)
        documents.append(tmp_dic)
    
    # Save complete documents to json
    with open('./documents/complete_documents.json', 'w', encoding='utf-8') as f:
        json.dump(documents, f, ensure_ascii=False, indent=4)


    # Because The sum of gpt4o input and output upper bound is 8000 tokens
    # The tokens to output 10 questions and answers are about 1000-2000 tokens
    # So here we filter documents with 2000-5000 tokens
    # If you want to process documents that have a lot of tokens, 
    # you need to split them up ahead of time
    # Check tokens(2000-5000)
    # In addition, documents containing Chinese are deleted
    filtered_documents_index = []
    for index in range(len(documents)):
        if documents[index]["tokens"] < 5000 and documents[index]["tokens"]>2000:
            if contains_chinese(documents[index]["content"]):continue
            else:
                filtered_documents_index.append(index)
    filtered_documents = [documents[i] for i in filtered_documents_index]

    # Save documents for generate dataset
    with open('./documents/documents_for_gen.json', 'w', encoding='utf-8') as f:
        json.dump(filtered_documents, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()