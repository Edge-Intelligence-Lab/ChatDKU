#TODO: Use LLM for automation


import pypdf
import re
import pandas as pd
from pathlib import Path
import argparse
import os

parser=argparse.ArgumentParser()
parser.add_argument("--corpus_path",help="Path for corpus",type=str,required=True)
parser.add_argument("--output_path",help="Path for output",type=str,required=True)
parser.add_argument("--max_iteration",default=3)


def extract_text_from_pdf(pdf_path):
    """Extract all text from the PDF."""
    text = ""
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def split_into_sections(text):
    """Split the text into sections based on 'Part X:' headings."""
    # Match lines starting with "Part X:" and capture content until next "Part X:" or end
    pattern = r'(Part\s+\d+[:\s]+.*?)(?=Part\s+\d+[:\s]+|\Z)'
    sections = re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if not sections:
        sections = [text]
    return sections

def extract_definitions(text_chunk):
    """Extract definition sentences containing patterns like 'is defined as', 'refers to', etc."""
    def_pattern = r'([A-Z][a-zA-Z\s]+?)\s+(?:is defined as|refers to|means)\s+([^.!?]*[.!?])'
    matches = re.findall(def_pattern, text_chunk, re.IGNORECASE)
    definitions = []
    for term, definition in matches:
        term = term.strip()
        definition = definition.strip()
        if len(term) > 1 and len(definition) > 10:
            definitions.append((term, definition))
    return definitions

def extract_courses(text_chunk):
    """Extract course codes and descriptions (e.g., 'ARTS 105 / PHYS 105 The Science...')."""
    course_pattern = r'([A-Z]{2,}\s+\d+[A-Z]?(?:\s*/\s*[A-Z]{2,}\s+\d+)?)\s+(.+?)(?=\n|$)'
    matches = re.findall(course_pattern, text_chunk)
    courses = []
    for code, desc in matches:
        code = code.strip()
        desc = desc.strip()
        if len(code) > 2 and len(desc) > 10:
            courses.append((code, desc))
    return courses

def generate_qa_from_section(section_title, section_text,max_iter):
    if not max_iter:
        max_iter=5
    """Generate question-answer pairs from a section."""
    qa_pairs = []
    # 1. Generate a broad question from the section title
    title_clean = re.sub(r'Part\s+\d+[:\s]+', '', section_title).strip()
    if title_clean:
        qa_pairs.append({
            "question": f"What is {title_clean}?",
            "ground_truth": section_text[:500] + "...",  # first 500 chars as rough answer
            "max_iteration": max_iter
        })
    # 2. Extract definitions
    for term, definition in extract_definitions(section_text):
        qa_pairs.append({
            "question": f"What is {term}?",
            "ground_truth": definition,
            "max_iteration": max_iter
        })
    # 3. Extract course descriptions
    for code, desc in extract_courses(section_text):
        qa_pairs.append({
            "question": f"What is {code}?",
            "ground_truth": desc,
            "max_iteration": max_iter
        })
    return qa_pairs

def main():
    args=parser.parse_args()
    corpus_path= os.path.abspath(args.corpus_path)
    full_text = extract_text_from_pdf(corpus_path)

    sections = split_into_sections(full_text)

    all_qa = []
    for i, section in enumerate(sections):
        first_line = section.split('\n')[0].strip()
        title = first_line if first_line else f"Section {i+1}"
        qa_list = generate_qa_from_section(title, section,max_iter=args.max_iteration)
        all_qa.extend(qa_list)

    # Remove duplicates based on question text
    df = pd.DataFrame(all_qa).drop_duplicates(subset=["question"])
    output_path=os.path.abspath(args.output_path)

    df.to_parquet(output_path, index=False)
    print(f"Dataset saved to {args.output_path}")  # kept as essential information

if __name__ == "__main__":
    main()
