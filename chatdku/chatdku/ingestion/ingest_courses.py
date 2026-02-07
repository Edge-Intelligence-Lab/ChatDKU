import hashlib
import logging
import re
from pathlib import Path
from queue import Queue
from threading import Thread

import chromadb
from chromadb.utils.embedding_functions import HuggingFaceEmbeddingServer
from pypdf import PdfReader

from chatdku.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

log = logging.getLogger(__file__)
log.setLevel(logging.INFO)


def reader_worker(pdf_path, buffer: Queue):
    """Extract and parse course information from PDF, then enqueue each course.

    This implementation uses a *sliding‑window* of two pages so that a description
    that is split across a page break can be captured in full.  The course is
    attributed to the page where its title (the course code line) appears.
    """

    # Extract text from PDF
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    # Regex pattern to match course entries
    pattern = r"((?:[A-Z]+\s+\d{3})(?:/[A-Z]+\s+\d{3})*)\s+([^\(]+?)\s*\((\d+)\s+credits?\)(.*?)(?=\n(?:[A-Z]+\s+\d{3}(?:/[A-Z]+\s+\d{3})*)\s+|$)"

    matches = re.finditer(pattern, text, re.DOTALL)

    for match in matches:
        course_code = match.group(1).strip()
        course_name = match.group(2).strip()
        credits = match.group(3).strip()
        full_text = match.group(4).strip()

        # Extract prerequisites
        prereq_pattern = (
            r"((?:Prerequisite\(s\)|Pre/Co-requisite\(s\)):\s*.+?)(?=\n\n|\Z)"
        )
        prereq_match = re.search(prereq_pattern, full_text, re.DOTALL)
        prerequisites = prereq_match.group(1).strip() if prereq_match else None
        # Remove unwanted 'Back to TOC' and following page numbers if present
        if prerequisites:
            prerequisites = re.sub(
                r"Back to TOC.*", "", prerequisites, flags=re.DOTALL
            ).strip()

        # Extract description (everything before prerequisites)
        if prerequisites:
            # Split on either format
            desc_split = re.split(
                r"(?:Prerequisite\(s\)|Pre/Co-requisite\(s\)):", full_text
            )
            description = desc_split[0].strip()
        else:
            description = full_text.strip()

        buffer.put(
            {
                "course_code": course_code,
                "course_name": course_name,
                "credits": credits,
                "description": description,
                "prerequisites": prerequisites,
                "file_name": Path(pdf_path).name,
            }
        )

    buffer.put(None)


def embed_worker(buffer: Queue):
    client = chromadb.HttpClient(host="localhost", port=config.chroma_db_port)

    for col in client.list_collections():
        if col.name == config.courses_col:
            logging.info("Courses collection exists. Deleting.")
            client.delete_collection(config.courses_col)
    collection = client.get_or_create_collection(
        name=config.courses_col,
        embedding_function=HuggingFaceEmbeddingServer(
            url=config.tei_url + "/" + config.embedding + "/embed"
        ),  # type: ignore
    )
    while True:
        course = buffer.get()

        if course is None:
            log.info("Buffer Empty. Exiting.")
            break

        log.info(f"Adding course: {course.get('course_code')}")
        text = str(
            {
                "course_code": course.get("course_code"),
                "course_name": course.get("course_name"),
                "credits": course.get("credits"),
                "description": course.get("description"),
                "prerequisites": course.get("prerequisites"),
            }
        )
        id = hashlib.md5(text.encode()).hexdigest()
        collection.add(
            ids=[id],
            documents=[text],
            metadatas=[
                {
                    "file_name": course.get("file_name"),
                    "course_code": course.get("course_code"),
                    "course_name": course.get("course_name"),
                }
            ],
        )


# Main function
def pipeline(path: str, output_json: str = "majors.json") -> None:
    """Reader, writer pipeline using threading"""

    buffer = Queue(maxsize=5)

    reader_thread = Thread(target=reader_worker, args=(path, buffer))
    embed_thread = Thread(target=embed_worker, args=(buffer,))

    reader_thread.start()
    embed_thread.start()

    reader_thread.join()
    embed_thread.join()

    log.info("Done!")


if __name__ == "__main__":
    input_dir = input("Enter the directory path: ")
    pipeline(path=input_dir)
