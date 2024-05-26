#!/usr/bin/env python3

import os
import html2markdown


def convert_html_to_markdown(html_file_path, md_file_path):
    with open(html_file_path, "r", encoding="utf-8") as html_file:
        html_content = html_file.read()
        md_content = html2markdown.convert(html_content)

    with open(md_file_path, "w", encoding="utf-8") as md_file:
        md_file.write(md_content)


def convert_all_html_in_directory(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".html") or file.endswith(".htm"):
                html_file_path = os.path.join(root, file)
                md_file_path = os.path.splitext(html_file_path)[0] + ".md"
                convert_html_to_markdown(html_file_path, md_file_path)
                print(f"Converted {html_file_path} to {md_file_path}")


if __name__ == "__main__":
    directory = "../RAG_data"  # Replace this path with your directory!!!!!!!!!!!
    convert_all_html_in_directory(directory)
