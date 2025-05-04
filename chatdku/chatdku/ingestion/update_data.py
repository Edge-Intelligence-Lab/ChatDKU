import os
import nltk
import nest_asyncio

nest_asyncio.apply()

import pickle
import argparse
from llama_index.core import SimpleDirectoryReader
from llama_index.core.readers.base import BaseReader
from llama_index.readers.file import UnstructuredReader
from llama_parse import LlamaParse
from chatdku.config import config
from markdownify import markdownify as md
from tqdm import tqdm
from pathlib import Path
from typing import Any, Dict, List, Optional
from llama_index.core.schema import Document
import pandas as pd
from openpyxl import load_workbook
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
)


# Override detect_filetype so that html files containing JavaScript code are loaded in html format.
import unstructured.file_utils.filetype
from custom_filetype_detect import custom_detect_filetype

unstructured.file_utils.filetype.detect_filetype = custom_detect_filetype

# Override auto partation
import unstructured.partition.auto
from custom_partation import partition

unstructured.partition.auto.partition = partition

import hashlib

text_splitter = RecursiveCharacterTextSplitter(
    separators=[
        "\n\n",
        "\n",
        ".",
        ",",
        "\u200b",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
        "?",
    ],
    chunk_size=490,
    chunk_overlap=20,
    length_function=len,
    is_separator_regex=False,
)



class XlsxReader(BaseReader):
    def __init__(
        self,
    ) -> None:
        super().__init__()

    
    def xlsx_load(self,file: Path) -> str:
        wb = load_workbook(file)
        # 获取所有工作表的名称
        sheet_names = wb.sheetnames

        markdown_menu = ""

        # 遍历每一个工作表
        for sheet_name in sheet_names:
            sub_wb = wb[sheet_name]
            merged_cells = list(sub_wb.merged_cells.ranges)  # 转换为列表
            
            # 遍历每一个合并单元格
            for merged_cell in merged_cells:
                min_row, max_row = merged_cell.min_row, merged_cell.max_row
                min_col, max_col = merged_cell.min_col, merged_cell.max_col
                
                # 获取合并单元格的值
                cell_value = sub_wb.cell(row=min_row, column=min_col).value
                
                # 解除合并单元格
                sub_wb.unmerge_cells(start_row=min_row, start_column=min_col, end_row=max_row, end_column=max_col)
                
                # 将值填充到之前合并单元格的所有单元格中
                for col in range(min_col, max_col + 1):
                    for row in range(min_row, max_row + 1):
                        sub_wb.cell(row=row, column=col, value=cell_value)

            data = wb[sheet_name].values
            columns = next(data)[0:]  # 获取第一行作为列名
            df = pd.DataFrame(data, columns=columns)
            
            # 处理 DataFrame 中的回车符
            df = df.applymap(lambda x: str(x).replace('\n', ' ') if isinstance(x, str) else x)
            
            # 去掉全为空值的行和列
            df.dropna(how='all', inplace=True)
            df.dropna(axis=1, how='all', inplace=True)

            # 去掉全为 None 的行和列
            df = df.applymap(lambda x: None if x == 'None' else x)
            df.dropna(how='all', inplace=True)
            df.dropna(axis=1, how='all', inplace=True)

            # 将 DataFrame 转换为 Markdown 格式
            markdown_output = df.to_markdown(index=False)
            markdown_menu += sheet_name + "菜单：\n"
            markdown_menu += markdown_output
            markdown_menu += "\n\n\n\n"

        return markdown_menu


    def load_data(
        self, file: Path, extra_info: Optional[Dict] = None
    ) -> List[Document]:
        docs = []
        metadata = {
            "file_name": file.name,
            "file_path": str(file),
        }
        if extra_info is not None:
            metadata.update(extra_info)

        return [Document(text=self.xlsx_load(file), metadata=metadata or {})]




def hash_file(filename):
    h = hashlib.sha256()
    with open(filename, "rb") as file:
        while True:
            chunk = file.read(h.block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_directory(directory):
    all_hashes = ""
    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            file_hash = hash_file(filepath)
            all_hashes += file_hash
    final_hash = hashlib.sha256(all_hashes.encode("utf-8")).hexdigest()
    return final_hash


def update_data(data_dir):
    # Required for UnstructuredReader
    # nltk.download("averaged_perceptron_tagger")
    reader = UnstructuredReader()

    documents_path = "/datapool/chat_dku_advising/New_parsed.pkl"


    reader = UnstructuredReader()
    xlsx_reader = XlsxReader()
    llama_parse_api_key = "llx-ruUEWvib0ZlDnk75bwLWfvNh1x117Kl2Z6ecpPL0tLLnJMdK"
    pdf_parser = LlamaParse(
        api_key=llama_parse_api_key,
        result_type="markdown",
        verbose=True,
    )
    documents = SimpleDirectoryReader(
        data_dir,
        recursive=True,
        required_exts=[".html", ".htm", ".pdf", ".csv", ".jpg", ".xlsx"],
        file_extractor={
            ".htm": reader,
            ".html": reader,
            ".csv": reader,
            ".jpg": reader,
            ".xlsx": xlsx_reader,
        },
    ).load_data()

    # deal with pdf
    for filename in os.listdir(data_dir):
        file_path = os.path.join(data_dir, filename)
        pdf_documents=[]
        if filename.endswith(".pdf"):
            pdf_loader = PyPDFLoader(file_path)
            for page in pdf_loader.load():
                entry = text_splitter.split_text(page.page_content)
                for chunk in entry:
                    add_chunk(chunk, filename, page.metadata.get("page", "N/A"))

    for doc in documents:
        if doc.metadata["file_type"] == "text/html":
            with open(doc.metadata["file_path"], "r") as f:
                html = f.read()
            try:
                doc.text = md(html)
            except:
                print(f"fail trans to md:{doc.metadata['file_path']}")

    with open(documents_path, "wb") as f:
        pickle.dump(documents, f)
    print(f"Documents stored in {documents_path}")
    print("Length of documents:", len(documents))
    return documents

# def update_sub_data():
    reader = UnstructuredReader()

    documents_path = "sub_documents.pkl"  # 这里可以根据需要修改路径

    llama_parse_api_key = "llx-ruUEWvib0ZlDnk75bwLWfvNh1x117Kl2Z6ecpPL0tLLnJMdK"
    pdf_parser = LlamaParse(
        api_key=llama_parse_api_key,
        result_type="markdown",
        verbose=True,
    )

    with open('/home/Glitterccc/ChatDKU/RAG/sub_data_list.pkl', 'rb') as f:
        file_paths = pickle.load(f)

    documents = []

    num = 0
    for file_path in tqdm(file_paths):
        try:
            # 检查文件扩展名并处理
            num += 1
            if file_path.endswith((".html", ".htm", ".pdf", ".csv",".jpg",".jpeg",".png",".docx",".doc")):
                if file_path.endswith((".htm", ".html")):
                    doc = reader.load_data(file_path)
                elif file_path.endswith(".pdf"):
                    doc = pdf_parser.parse(file_path)
                elif file_path.endswith(".csv"):
                    doc = reader.load_data(file_path)
                elif file_path.endswith(".jpg"):
                    doc = reader.load_data(file_path)
                elif file_path.endswith(".jpeg"):
                    doc = reader.load_data(file_path)
                elif file_path.endswith(".png"):
                    doc = reader.load_data(file_path)
                elif file_path.endswith((".docx",".doc")):
                    doc = reader.load_data(file_path)
                if len(doc) != 1:
                    print('-------Wrong----')
                    print(doc)
                doc = doc[0]
                # 处理文档
                if doc.metadata["filetype"] == "text/html":
                    with open(file_path, "r") as f:
                        html = f.read()
                    try:
                        doc.text = md(html)
                    except Exception as e:
                        print(f"Failed to convert to markdown: {file_path}, Error: {e}")

                documents.append(doc)
        except:
            continue

        with open(documents_path, "wb") as f:
            pickle.dump(documents, f)

    with open(documents_path, "wb") as f:
        pickle.dump(documents, f)

    print(f"Documents stored in {documents_path}")
    print("Length of documents:", len(documents))
    return documents


def main(data_dir=None):
    if data_dir is None:
        data_dir = config.data_dir

    update_data(data_dir)
    hash = hash_directory(data_dir)
    hash_path = os.path.join("./", "hash.pkl")
    with open(hash_path, "wb") as hf:
        pickle.dump(hash, hf)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process data directory path")
    parser.add_argument("data_dir", type=str, help="The directory containing the data")
    args = parser.parse_args()

    main(args.data_dir)
