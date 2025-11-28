import os
import datetime
from bs4 import BeautifulSoup, NavigableString
from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import Document


class HtmlCleaner(BaseReader):
    def load_data(self, file, extra_info=None):
        try:
            with open(file, "r", encoding="utf-8") as f:
                html = f.read()
        except Exception as e:
            print(f"[ERROR] Cannot read file: {file} | {e}")
            return []

        soup = BeautifulSoup(html, "lxml")
        
        self._remove_noise_tags(soup)
        self._remove_keywords_nodes(soup)
        self._remove_empty_tags(soup)

        self._preserve_links(soup)
        main_text = self._extract_main_text(soup)
        main_text = self._clean_text(main_text)

        metadata = {
            "source_file_name": os.path.basename(file),
            "source_file_path": str(file),
        }
        if extra_info:
            metadata.update(extra_info)

        return [Document(text=main_text, metadata=metadata)]

    def _remove_noise_tags(self, soup):
        noise_tags = [
            "script", "style", "meta", "noscript", "header", "footer",
            "nav", "aside", "iframe", "svg", "link"
        ]
        for tag in soup.find_all(noise_tags):
            tag.decompose()

    def _remove_keywords_nodes(self, soup):
        keywords = [
            "cookie", "popup", "banner", "subscribe",
            "alert", "modal", "advert", "ads", "tracking"
        ]
        for tag in soup.find_all(["div", "span", "section"]):
            text = tag.get_text(" ", strip=True).lower()
            if any(k in text for k in keywords):
                tag.decompose()

    def _remove_empty_tags(self, soup):
        for tag in soup.find_all():
            if isinstance(tag, NavigableString):
                continue
            text = tag.get_text(strip=True)
            if not text:
                tag.decompose()
    
    def _preserve_links(self, soup):
        KEEP_LINK_PATTERNS = [
            "calendar.dukekunshan.edu.cn/event",  # canonical event page
            ]
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(pattern in href for pattern in KEEP_LINK_PATTERNS):
                a.replace_with(f"{a.get_text(strip=True)} ({href})")
            else:
                a.unwrap()  

    def _extract_main_text(self, soup):
        main_candidate = (
            soup.find("main")
            or soup.find(attrs={"role": "main"})
            or soup.find("article")
        )
        if main_candidate:
            return main_candidate.get_text("\n")

        candidates = soup.find_all(["div", "section", "article"], recursive=True)
        best_node = None
        best_score = 0

        for node in candidates:
            text = node.get_text(" ", strip=True)
            score = len(text)
            if score > best_score:
                best_score = score
                best_node = node

        if best_node:
            return best_node.get_text("\n")

        return soup.get_text("\n")

    def _clean_text(self, text):
        if not text:
            return ""

        lines = [line.strip() for line in text.split("\n")]

        cleaned = []
        for line in lines:
            if not line:
                continue
            if len(line) <= 1 and not line.isalnum():
                continue
            cleaned.append(line)

        final_lines = []
        prev = None
        for line in cleaned:
            if line != prev:
                final_lines.append(line)
            prev = line

        return "\n".join(final_lines)


# -----------------------------------------------------------
# Main entry for testing
# -----------------------------------------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test HtmlCleaner")
    parser.add_argument("html_file", help="Path to an HTML file to clean")
    args = parser.parse_args()

    cleaner = HtmlCleaner()
    docs = cleaner.load_data(args.html_file)

    if not docs:
        print("[INFO] No output documents.")
        return

    for idx, doc in enumerate(docs):
        print("=" * 50)
        print(f"[Document #{idx}]")
        print("--- Metadata ---")
        for k, v in doc.metadata.items():
            print(f"{k}: {v}")
        print("\n--- Cleaned Text ---")
        print(doc.text[:2000])  # show first 2k chars
        print("=" * 50)


if __name__ == "__main__":
    main()