from llama_index import Document, LlamaIndex
import PyPDF2
import json

def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfFileReader(file)
        for page_num in range(reader.numPages):
            page = reader.getPage(page_num)
            text += page.extract_text()
    return text

pdf_path = "/mnt/data/2024-06-15-12-AZXtzkzoYsm6W0PlItbR.pdf"
pdf_text = extract_text_from_pdf(pdf_path)

metadata = {
    "source": "Duke Kunshan University Student Handbook",
    "type": "Policy Document",
    "sections": {
        "introduction": ["SECTION 1", "INTRODUCTION"],
        "residential_experience": ["SECTION 2", "RESIDENTIAL EXPERIENCE"],
        "rights_and_responsibilities": ["SECTION 3", "RIGHTS AND RESPONSIBILITIES"],
        "university_policies": ["SECTION 4", "UNIVERSITY POLICIES"]
    }
}

doc = Document(text=pdf_text, metadata=metadata)

index = LlamaIndex()
index.add_document(doc)

def filter_documents_by_metadata(index, filter_criteria):
    filtered_docs = []
    for doc in index.documents:
        match = all(doc.metadata.get(key) == value for key, value in filter_criteria.items())
        if match:
            filtered_docs.append(doc)
    return filtered_docs

filter_criteria = {"type": "Policy Document"}
filtered_documents = filter_documents_by_metadata(index, filter_criteria)

for doc in filtered_documents:
    print(f"Title: {doc.metadata['source']}")
    print(doc.text[:500])  # Print first 500 characters of the document text

def query_index_with_filters(index, query, filter_criteria):
    filtered_docs = filter_documents_by_metadata(index, filter_criteria)
    results = []
    for doc in filtered_docs:
        if query.lower() in doc.text.lower():
            results.append(doc)
    return results

query = "residential experience"
filter_criteria = {"type": "Policy Document"}

results = query_index_with_filters(index, query, filter_criteria)
for result in results:
    print(f"Found in: {result.metadata['source']}")
    print(result.text[:500])  # Print first 500 characters of the result text
