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

    This version processes the PDF page‑by‑page, determines the originating page
    number for each course, and attempts to append any description text that may be
    cut off at a page break by peeking at the following page.
    """

    # Load PDF and collect page texts
    reader = PdfReader(pdf_path)
    page_texts: list[str] = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        page_texts.append(txt)

    # Build a single string for regex matching while keeping offsets
    full_text = "\n".join(page_texts)
    # Compute cumulative character offsets for each page start
    offsets: list[int] = []
    cum = 0
    for txt in page_texts:
        offsets.append(cum)
        cum += len(txt) + 1  # +1 for the newline we inserted

    # Regex pattern to match course entries
    pattern = r"((?:[A-Z]+\s+\d{3})(?:/[A-Z]+\s+\d{3})*)\s+([^\(]+?)\s*\((\d+)\s+credits?\)(.*?)(?=\n(?:[A-Z]+\s+\d{3}(?:/[A-Z]+\s+\d{3})*)\s+|$)"

    matches = re.finditer(pattern, full_text, re.DOTALL)

    for match in matches:
        # Determine which page this match starts on
        start_pos = match.start()
        page_idx = 0
        for i, off in enumerate(offsets):
            if start_pos >= off:
                page_idx = i
        # Extract basic fields
        course_code = match.group(1).strip()
        course_name = match.group(2).strip()
        credits = match.group(3).strip()
        full_course_text = match.group(4).strip()

        # Extract prerequisites
        prereq_pattern = (
            r"((?:Prerequisite\(s\)|Pre/Co-requisite\(s\)):\s*.+?)(?=\n\n|\Z)"
        )
        prereq_match = re.search(prereq_pattern, full_course_text, re.DOTALL)
        prerequisites = prereq_match.group(1).strip() if prereq_match else None
        if prerequisites:
            prerequisites = re.sub(
                r"Back to TOC.*", "", prerequisites, flags=re.DOTALL
            ).strip()

        # Extract description (everything before prerequisites)
        if prerequisites:
            desc_split = re.split(
                r"(?:Prerequisite\(s\)|Pre/Co-requisite\(s\)):", full_course_text
            )
            description = desc_split[0].strip()
        else:
            description = full_course_text.strip()

        # If description seems truncated (no trailing period) and there is a next page,
        # append the next page's text as a simple heuristic.
        if (
            description
            and not description.endswith(".")
            and page_idx + 1 < len(page_texts)
        ):
            continuation = page_texts[page_idx + 1].strip()
            if continuation:
                description = description + " " + continuation

        # Build course dict including metadata
        course = {
            "course_code": course_code,
            "course_name": course_name,
            "credits": credits,
            "description": description,
            "prerequisites": prerequisites,
            "page_number": page_idx + 1,  # make it 1‑based for readability
            "file_name": Path(pdf_path).name,
        }
        # Enqueue for embedding worker
        buffer.put(course)

    # Signal completion to the embedding worker
    buffer.put(None)

    # No return value – work is done via the queue
    return None


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
        ),
    )
    while True:
        course = buffer.get()

        if course is None:
            log.info("Buffer Empty. Exiting.")
            break

        log.info(f"Adding course: {course.get('course_code')}")
        text = str(course)
        id = hashlib.md5(text.encode()).hexdigest()
        reqs = course.get("prerequisites")
        collection.add(
            ids=[id],
            documents=[text],
            metadatas=[
                {
                    # TODO: Add URL
                    "file_name": course.get("file_name"),
                    "course_code": course.get("course_code"),
                    "course_name": course.get("course_name"),
                    "prerequisites": reqs if reqs else "None",
                    "page_number": course.get("page_number"),
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
    pipeline(folder=input_dir)
