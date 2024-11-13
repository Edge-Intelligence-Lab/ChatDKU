import pandas as pd
import pickle
from chatdku.config import Config

def documents_reprocess():
    with open(config.documents_path, "rb") as file:
        documents = pickle.load(file) 

    csv_path=config.csv_path

    urlinfo=pd.read_csv(csv_path)
    keys_to_keep = {"url", "file_path","last_modified_date"}

    for document in documents:

        document.text='\n'.join([line for line in document.text.split('\n') if line.strip() != ''])

        document_path=document.metadata["file_path"].replace("/opt/RAG_data/","")
        if document_path in urlinfo.iloc[:, 4].values:
            index = urlinfo[urlinfo.iloc[:, 4] == document_path].index[0]
            url = urlinfo.iloc[index, 3]
            document.metadata["url"]=url
    
        document.metadata={k: v for k, v in document.metadata.items() if k in keys_to_keep}

    with open(config.documents_path, "wb") as file:
        pickle.dump(documents,file) 

def main():
    documents_reprocess()

if __name__ == "__main__":
    main()
