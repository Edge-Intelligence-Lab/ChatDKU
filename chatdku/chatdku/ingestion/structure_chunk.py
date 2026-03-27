"""
Structure-aware PDF chunker using pdfplumber.
Detects heading levels and chunks hierarchically to preserve document structure.
"""

import re
import pdfplumber
from typing import List, Dict, Any
from llama_index.core.schema import Document


def pdf_to_items(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Parse PDF and extract text lines with detected heading levels.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of dictionaries, each containing:
            - text: The line text
            - level: Heading level (0=normal text, 1=level1 heading, 2=level2, 3=level3)
            - page: Page number
    """
    items = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            
            chars = page.chars if page.chars else []
            lines = text.split('\n')
            
            font_sizes = [char.get('size', 0) for char in chars if char.get('size')]
            common_size = max(set(font_sizes), key=font_sizes.count) if font_sizes else 12
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                line_font_size = common_size
                if chars:
                    line_chars = [c for c in chars if c.get('text') and c['text'] in line]
                    if line_chars:
                        line_font_size = line_chars[0].get('size', common_size)
                
                level = detect_title_level(line, line_font_size, common_size)
                
                items.append({
                    "text": line,
                    "level": level,
                    "page": page_num
                })
    
    return items


def detect_title_level(text: str, font_size: float, default_size: float) -> int:
    """
    Detect heading level using heuristic rules.
    
    Rules (in priority order):
        1. All caps with moderate length -> level 1
        2. Numbered sections (1., 2.1, 3.2.1) -> level based on dot count
        3. Roman numerals (I., II., III.) -> level 1
        4. Chapter/Section/Part + number -> level 1
        5. Larger font size -> level 1 or 2 based on size ratio
        6. Ends with colon or em dash -> level 2
        
    Args:
        text: The text line to analyze
        font_size: Font size of this line
        default_size: Common font size on the page
        
    Returns:
        Heading level (0=normal, 1=level1, 2=level2, 3=level3)
    """
    text_upper = text.upper()
    
    if text.isupper() and len(text) > 10 and len(text) < 100:
        return 1
    
    match = re.match(r'^(\d+(?:\.\d+)*)\.?\s+', text)
    if match:
        num_str = match.group(1)
        dot_count = num_str.count('.')
        if dot_count == 0:
            return 1
        elif dot_count == 1:
            return 2
        else:
            return 3
    
    if re.match(r'^[IVXLCDM]+\.\s+', text_upper):
        return 1
    
    if re.match(r'^(Chapter|Section|Part)\s+\d+', text, re.IGNORECASE):
        return 1
    
    if font_size > default_size * 1.2:
        if font_size > default_size * 1.5:
            return 1
        else:
            return 2
    
    if text.endswith(':') or text.endswith('——'):
        return 2
    
    return 0


def split_items_by_level(items: List[Dict], target_level: int, max_chunk_size: int) -> List[List[str]]:
    """
    Split a list of items by a specific heading level.
    
    Args:
        items: List of item dictionaries with 'text' and 'level' keys
        target_level: The heading level to split on (2 or 3)
        max_chunk_size: Maximum chunk size in characters (for future use)
        
    Returns:
        List of chunks, each chunk is a list of text lines
    """
    sub_chunks = []
    current_sub = []
    
    for item in items:
        level = item.get('level', 0)
        text = item.get('text', '')
        
        if not text:
            continue
        
        if level == target_level:
            if current_sub:
                sub_chunks.append(current_sub)
                current_sub = []
            current_sub.append(text)
        else:
            current_sub.append(text)
    
    if current_sub:
        sub_chunks.append(current_sub)
    
    return sub_chunks


def split_text_by_sentences(text_lines: List[str], max_chunk_size: int) -> List[List[str]]:
    """
    Split text by sentence boundaries for lines that exceed max_chunk_size.
    
    Args:
        text_lines: List of text lines
        max_chunk_size: Maximum chunk size in characters
        
    Returns:
        List of chunks, each chunk is a list of text lines/sentences
    """
    if not text_lines:
        return []
    
    total_text = '\n'.join(text_lines)
    if len(total_text) <= max_chunk_size:
        return [text_lines]
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for line in text_lines:
        line_size = len(line)
        
        if line_size > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0
            
            sentences = re.split(r'([。！？\.!\?])', line)
            sentence_parts = []
            for i in range(0, len(sentences) - 1, 2):
                if i + 1 < len(sentences):
                    sentence_parts.append(sentences[i] + sentences[i + 1])
            
            if not sentence_parts:
                sentence_parts = [line]
            
            sub_chunk = []
            sub_size = 0
            for sent in sentence_parts:
                sent_size = len(sent)
                if sub_size + sent_size > max_chunk_size:
                    if sub_chunk:
                        chunks.append(sub_chunk)
                    sub_chunk = [sent]
                    sub_size = sent_size
                else:
                    sub_chunk.append(sent)
                    sub_size += sent_size
            
            if sub_chunk:
                chunks.append(sub_chunk)
        else:
            if current_size + line_size > max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def structure_aware_chunking(
    items: List[Dict[str, Any]],
    max_chunk_size: int = 800,
    min_chunk_size: int = 80,
) -> List[List[str]]:
    """
    Perform structure-aware chunking on parsed PDF items.
    
    Strategy:
        1. Split by level-1 headings to create main sections
        2. If a section exceeds max_chunk_size, split by level-2 headings
        3. If still exceeds, split by level-3 headings
        4. If still exceeds, split by sentence boundaries
        5. Merge chunks smaller than min_chunk_size with previous chunk
    
    Args:
        items: List of item dictionaries from pdf_to_items()
        max_chunk_size: Maximum chunk size in characters
        min_chunk_size: Minimum chunk size for merging
        
    Returns:
        List of chunks, each chunk is a list of text lines
    """
    temp_list = []
    chunked_list = []
    prev_j = None
    
    for j, item in enumerate(items):
        if item.get('level') == 1:
            if len(temp_list) > 0:
                temp_text = '\n'.join(temp_list)
                if len(temp_text) > max_chunk_size:
                    sub_chunks = split_items_by_level(items[prev_j:j], 2, max_chunk_size)
                    chunked_list.extend(sub_chunks)
                else:
                    chunked_list.append(temp_list)
                temp_list = []
            prev_j = j
            temp_list.append(item.get('text', ''))
        else:
            text = item.get('text', '')
            if text:
                temp_list.append(text)
    
    if temp_list:
        temp_text = '\n'.join(temp_list)
        if len(temp_text) > max_chunk_size:
            sub_chunks = split_items_by_level(items[prev_j:], 2, max_chunk_size)
            chunked_list.extend(sub_chunks)
        else:
            chunked_list.append(temp_list)
    
    final_chunks = []
    for chunk in chunked_list:
        chunk_text = '\n'.join(chunk)
        if len(chunk_text) > max_chunk_size:
            sub_chunks = split_text_by_sentences(chunk, max_chunk_size)
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(chunk)
    
    filtered_chunks = []
    for chunk in final_chunks:
        chunk_text = ''.join(chunk)
        if len(chunk_text) >= min_chunk_size:
            filtered_chunks.append(chunk)
        else:
            if filtered_chunks:
                filtered_chunks[-1].extend(chunk)
            else:
                filtered_chunks.append(chunk)
    
    return filtered_chunks


def process_pdf(
    pdf_path: str,
    max_chunk_size: int = 800,
    min_chunk_size: int = 80,
) -> List[Document]:
    """
    Process a PDF file and return a list of Document objects.
    
    This is the main entry point for PDF processing. It:
        1. Parses the PDF and extracts text lines with heading levels
        2. Performs structure-aware chunking
        3. Converts chunks to LlamaIndex Document objects with metadata
    
    Args:
        pdf_path: Path to the PDF file
        max_chunk_size: Maximum chunk size in characters (default: 800)
        min_chunk_size: Minimum chunk size for merging (default: 80)
    
    Returns:
        List of Document objects, each containing a chunk of text
    """
    items = pdf_to_items(pdf_path)
    chunks = structure_aware_chunking(items, max_chunk_size, min_chunk_size)
    chunk_texts = [''.join(chunk) for chunk in chunks]
    
    documents = []
    for text in chunk_texts:
        doc = Document(
            text=text,
            metadata={
                "source": pdf_path,
                "chunking_method": "structure_aware",
                "is_pdf": True,
            }
        )
        documents.append(doc)
    
    return documents
