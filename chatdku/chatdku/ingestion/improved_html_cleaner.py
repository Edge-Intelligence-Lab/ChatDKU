import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from bs4 import BeautifulSoup, NavigableString
from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import Document

logger = logging.getLogger(__name__)


class HtmlCleaner(BaseReader):
    """
    HTML cleaner that extracts main text content and metadata from an HTML file.
    Behavior fully matches the original_cleaner.py.
    """

    DEFAULT_NOISE_TAGS = {
        "script", "style", "meta", "noscript", "header", "footer",
        "nav", "aside", "iframe", "svg", "link"
    }

    DEFAULT_KEYWORDS = {
        "cookie", "popup", "banner", "subscribe",
        "alert", "modal", "advert", "ads", "tracking"
    }

    DEFAULT_KEEP_LINK_PATTERNS = [
        "calendar.dukekunshan.edu.cn/event",
    ]

    def __init__(
        self,
        noise_tags: Optional[set] = None,
        noise_keywords: Optional[set] = None,
        keep_link_patterns: Optional[List[str]] = None,
        **kwargs
    ):
        self.noise_tags = noise_tags or self.DEFAULT_NOISE_TAGS
        self.noise_keywords = noise_keywords or self.DEFAULT_KEYWORDS
        self.keep_link_patterns = keep_link_patterns or self.DEFAULT_KEEP_LINK_PATTERNS

    def load_data(
        self,
        file: Union[str, Path],
        extra_info: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        file_path = Path(file)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    html = f.read()
                logger.warning(f"Used latin-1 fallback encoding for {file_path}")
            except Exception as e:
                logger.error(f"Cannot read file {file_path}: {e}")
                return []
        except Exception as e:
            logger.error(f"Cannot read file {file_path}: {e}")
            return []

        soup = BeautifulSoup(html, "lxml")

        canonical = self._extract_canonical(soup)

        self._remove_noise_tags(soup)
        self._remove_keywords_nodes(soup)         
        self._remove_empty_tags(soup)
        self._preserve_links(soup)                

        main_text = self._extract_main_text(soup)
        main_text = self._clean_text(main_text)

        metadata = {
            "source_file_name": file_path.name,
            "source_file_path": str(file_path),
        }
        if canonical:
            metadata["event_url"] = canonical
        if extra_info:
            metadata.update(extra_info)

        return [Document(text=main_text, metadata=metadata)]

    # ----------------------------------------------------------------------
    # Extraction helpers
    # ----------------------------------------------------------------------
    def _extract_canonical(self, soup: BeautifulSoup) -> Optional[str]:
        tag = soup.find("link", rel="canonical")
        if tag and tag.get("href"):
            return tag["href"]
        return None

    def _remove_noise_tags(self, soup: BeautifulSoup) -> None:
        for tag in soup.find_all(self.noise_tags):
            tag.decompose()

    def _remove_keywords_nodes(self, soup: BeautifulSoup) -> None:
        """
        Remove div/span/section whose text contains any noise keyword.
        """
        keywords_lower = {k.lower() for k in self.noise_keywords}
        for tag in soup.find_all(["div", "span", "section"]):
            if tag is None or tag.parent is None:
                continue
            text = tag.get_text(" ", strip=True).lower()
            if any(k in text for k in keywords_lower):
                tag.decompose()

    def _remove_empty_tags(self, soup: BeautifulSoup) -> None:
        for tag in soup.find_all(True):
            if isinstance(tag, NavigableString):
                continue
            # Use stripped_strings for efficiency
            try:
                if not any(tag.stripped_strings):
                    tag.decompose()
            except (AttributeError, RuntimeError):
                continue

    def _preserve_links(self, soup: BeautifulSoup) -> None:
        """
        Process <a> tags:
        - If href contains any keep pattern, replace with "text (url)".
        - Otherwise, unwrap the tag (keep inner text but remove <a>).
        """
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(pattern in href for pattern in self.keep_link_patterns):
                text = a.get_text(strip=True)
                a.replace_with(f"{text} ({href})")
            else:
                a.unwrap()

    def _extract_main_text(self, soup: BeautifulSoup) -> str:
        # Try semantic tags first
        main_candidate = (
            soup.find("main")
            or soup.find(attrs={"role": "main"})
            or soup.find("article")
        )
        if main_candidate:
            return main_candidate.get_text("\n")

        # Fallback: choose the div/section/article with the longest text
        candidates = soup.find_all(["div", "section", "article"], recursive=True)
        best_node = None
        best_score = 0
        for node in candidates:
            text = node.get_text(" ", strip=True)
            score = len(text)
            if score > best_score and score >= 50:
                best_score = score
                best_node = node

        if best_node:
            return best_node.get_text("\n")

        # Last resort: whole document
        return soup.get_text("\n")

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""

        lines = text.splitlines()
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if len(line) <= 1 and not line.isalnum():
                continue
            cleaned.append(line)

        # Remove consecutive duplicate lines
        final_lines = []
        prev = None
        for line in cleaned:
            if line != prev:
                final_lines.append(line)
            prev = line

        return "\n".join(final_lines)
