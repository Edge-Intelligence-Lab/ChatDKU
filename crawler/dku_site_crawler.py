import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

OUTPUT_ROOT = "site"
MAX_DEPTH = 3


def scrape_site(url, depth=0):
    if depth > MAX_DEPTH:
        return

    a = urlparse(url)
    filename = os.path.join(OUTPUT_ROOT, a.path.lstrip("/"), "index.txt")
    # Don't scrape the same page twice
    if os.path.isfile(filename):
        return

    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to download: {url}")
        return

    soup = BeautifulSoup(response.content, "html.parser")
    text = soup.get_text()

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as file:
        file.write(text)
    print(f"Downloaded: {url}")

    links = soup.find_all("a", href=True)
    for link in links:
        href = link.get("href")
        # Make sure it's a relative URL
        if href.startswith("/"):
            absolute_url = urljoin(url, href)
        else:
            absolute_url = url
        scrape_site(absolute_url, depth + 1)


if __name__ == "__main__":
    scrape_site("https://dukekunshan.edu.cn")
