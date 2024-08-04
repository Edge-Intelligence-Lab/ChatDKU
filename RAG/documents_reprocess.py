
import pandas as pd
import pickle
from settings import Config
config=Config()

def main():
    with open(config.documents_path, "rb") as file:
        documents = pickle.load(file) 

    csv_path=config.csv_path

    urlinfo=pd.read_csv(csv_path)

    for document in documents:

        document.text='\n'.join([line for line in document.text.split('\n') if line.strip() != ''])

        document_path=document.metadata["file_path"].replace("/opt/RAG_data","")
        if document_path in urlinfo.iloc[:, 4].values:
            index = urlinfo[urlinfo.iloc[:, 4] == document_path].index[0]
            url = urlinfo.iloc[index, 3]
            document.metadata["url"]=url
    

if __name__ == "__main__":
    main()
