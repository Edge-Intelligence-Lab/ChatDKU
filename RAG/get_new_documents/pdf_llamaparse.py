import os
import nest_asyncio
nest_asyncio.apply()
from llama_parse import LlamaParse
from tqdm import tqdm
import pickle

llama_parse_api_key = "llx-3seoejMfWBXdMv6herqrsJAXVakAbm2sWLF31Mmzhr6di8lc"

def is_pdf_file(file_path):
    # 判断文件是否是以 .pdf 结尾的文件
    return os.path.isfile(file_path) and file_path.lower().endswith('.pdf')

def search_pdfs_in_directory(directory_path):
    pdf_files = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            if is_pdf_file(file_path):
                pdf_files.append(file_path)
    return pdf_files

def main():
    directory_path = "/home/Glitterccc/projects/DKU_LLM/RAG_data"  # 替换为你的目标文件夹路径
    pdf_files = search_pdfs_in_directory(directory_path)
    parser = LlamaParse(
        api_key=llama_parse_api_key,  # can also be set in your env as LLAMA_CLOUD_API_KEY
        result_type="markdown",  # "markdown" and "text" are available
        num_workers=4,  # if multiple files passed, split in `num_workers` API calls
        verbose=True,
        language="en",  # Optionally you can define a language, default=en
    )
    with open('pdf_files.pkl', 'wb') as f:
        pickle.dump(pdf_files, f)

    document_list = []
    for pdf_file in tqdm(pdf_files):
        try:
            documents = parser.load_data(pdf_file)
            print(documents)
        except:
            print(f"{pdf_file} failed")
        document_list.append(documents)

    with open('pdf_documents.pkl', 'wb') as f:
        pickle.dump(document_list, f)

if __name__ == "__main__":
    main()