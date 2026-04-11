#!/usr/bin/env python3
"""
Major Ingest Tool

Extracts major requirements from student bulletin PDF files using PyMuPDF.
Splits the PDF by major and outputs each major's content as a markdown file.
"""

import argparse
import re
from pathlib import Path
from typing import Dict, List

try:
    import fitz  # PyMuPDF
    import pymupdf4llm
except ImportError as e:
    raise ImportError(
        "PyMuPDF and PyMuPDF4LLM are required. Install with: pip install pymupdf pymupdf4llm"
    ) from e


MAJORS_TO_EXTRACT: List[str] = [
    "Requirements for All Majors",
    "Applied Mathematics and Computational Sciences/Computer Science",
    "Applied Mathematics and Computational Sciences/Mathematics",
    "Arts and Media/Arts",
    "Arts and Media/Media",
    "Behavioral Science / Economics",
    "Behavioral Science / Psychology",
    "Behavioral Science / Neuroscience",
    "Computation and Design / Computer Science",
    "Computation and Design / Digital Media",
    "Computation and Design / Social Policy",
    "Cultures and Societies / Cultural Anthropology",
    "Cultures and Movements / Religious Studies",
    "Cultures and Movements / World History",
    "Cultures and Societies / Sociology",
    "Data Science",
    "Environmental Science / Biogeochemistry",
    "Environmental Science / Biology",
    "Environmental Science / Chemistry",
    "Environmental Science / Public Policy",
    "Ethics and Leadership / Philosophy",
    "Ethics and Leadership / Public Policy",
    "Institutions and Governance / Economics",
    "Institutions and Governance / Political Science",
    "Institutions and Governance / Public Policy",
    "Global China Studies / Chinese History",
    "Global China Studies / Political Science",
    "Global China Studies / Religious Studies",
    "Global Cultural Studies / Creative Writing and Translation",
    "Global Cultural Studies / World History",
    "Global Cultural Studies / World Literature",
    "Global Health / Biology",
    "Global Health / Public Policy",
    "Humanities / Creative Writing and Translation",
    "Humanities / Literature",
    "Humanities /Philosophy and Religion",
    "Humanities /World History",
    "Materials Science / Chemistry",
    "Materials Science / Physics",
    "Molecular Bioscience / Biogeochemistry",
    "Molecular Bioscience / Biophysics",
    "Molecular Bioscience / Cell and Molecular Biology",
    "Molecular Bioscience / Genetics and Genomics",
    "Molecular Bioscience / Neuroscience",
    "Political Economy / Economics",
    "Political Economy / Political Science",
    "Political Economy / Public Policy",
    "US Studies / American History",
    "US Studies / American Literature",
    "US Studies / Political Science",
    "US Studies / Public Policy",
    "Philosophy, Politics, and Economics / Economic History",
    "Philosophy, Politics, and Economics / Philosophy",
    "Philosophy, Politics, and Economics / Political Science",
    "Philosophy, Politics, and Economics / Public Policy",
    "Quantitative Political Economy / Economics",
    "Quantitative Political Economy /Political Science",
    "Quantitative Political Economy /Public Policy",
]


def extract_majors(
    pdf_path: str, page_start: int, majors: List[str]
) -> Dict[str, Dict]:
    doc = fitz.open(pdf_path)
    major_contents: Dict[str, dict] = {}
    current_major: str = ""

    course_code_pattern = re.compile(r"\b[A-Z]{2,10}\s+\d{1,3}\b", re.IGNORECASE)

    end_pattern = re.compile(r"Course Descriptions", re.IGNORECASE)

    another_end_pattern = re.compile(
        r"Majors (listed in alphabetical order)", re.IGNORECASE
    )

    def make_major_pattern(major: str) -> re.Pattern:
        return re.compile(
            rf"{re.escape(major)}",
            re.IGNORECASE,
        )

    for page_num in range(page_start - 1, len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()

        if end_pattern.search(text):
            break
        if another_end_pattern.search(text):
            break

        for major in majors:
            major_pattern = make_major_pattern(major)
            if major_pattern.search(text):
                current_major = major
                print(f"Found major: {current_major}")
                major_contents[current_major] = {"md": ""}
                break

        if current_major:
            # NOTE:Check if the page contains a course code
            # Without this, it was returning the next major's
            # descriptions, which was irrelevant to the current major
            if course_code_pattern.search(text):
                md_text = pymupdf4llm.to_markdown(doc, pages=[page_num], use_ocr=False)
                major_contents[current_major]["md"] += md_text

    doc.close()
    return major_contents


def sanitize_filename(name: str) -> str:
    """Convert a major name to a safe filename."""
    # Remove or replace unsafe characters
    safe = re.sub(r"[^\w\s-]", "", name)
    safe = re.sub(r"[-\s]+", "-", safe)
    return safe.strip("-").lower()


def save_major_content(major_name: str, content: Dict, output_dir: Path):
    """Save a major's content to a markdown file."""
    filename = sanitize_filename(major_name) + ".md"
    output_path = output_dir / filename

    # Build markdown content
    md_lines = [
        f"# {major_name}",
        "",
        "## Requirements",
        "",
        content.get("md", ""),
    ]

    # Write to file
    output_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Saved: {output_path}")


def run_ingest(pdf_path: str, start_page: int, output_dir: str) -> int:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return 1

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    if start_page < 1 or start_page > total_pages:
        return 1

    out_dir = Path(output_dir) / pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    if not MAJORS_TO_EXTRACT:
        return 0

    major_contents = extract_majors(pdf_path, start_page, MAJORS_TO_EXTRACT)

    saved_count = 0
    for major, content in major_contents.items():
        if content.get("md"):
            save_major_content(major, content, out_dir)
            saved_count += 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Extract major requirements from student bulletin PDF"
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "start_page", type=int, help="Page number to start parsing from (1-indexed)"
    )
    parser.add_argument("output_dir", help="Directory to output markdown files")

    args = parser.parse_args()

    # Validate PDF path
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        return 1

    # Validate start page
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    if args.start_page < 1 or args.start_page > total_pages:
        print(f"Error: Start page must be between 1 and {total_pages}")
        return 1

    # Create output directory named after the input file
    output_dir = Path(args.output_dir) / pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine majors to extract
    majors_to_extract = MAJORS_TO_EXTRACT

    if not majors_to_extract:
        print(
            "Warning: No majors specified. Use --major flag or populate MAJORS_TO_EXTRACT list."
        )
        return 0

    print(f"Extracting content for {len(majors_to_extract)} majors...")
    print(f"Starting from page {args.start_page} of {pdf_path}")

    # Extract content
    major_contents = extract_majors(pdf_path, args.start_page, majors_to_extract)

    # Save each major to file
    saved_count = 0
    for major, content in major_contents.items():
        if content.get("md"):
            save_major_content(major, content, output_dir)
            saved_count += 1
        else:
            print(f"Warning: No content found for major '{major}'")

    print(f"\nExtraction complete. Saved {saved_count} major(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    exit(main())
