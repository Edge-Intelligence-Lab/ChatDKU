#!/usr/bin/env python3

import os
import random
import asyncio
import aiohttp
from aiohttp_retry import RetryClient, ExponentialRetry
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

OUTPUT_ROOT = "dku_website"
MAX_DEPTH = 5

# Paths of downloaded files are used to ensure uniqueness
downloaded = set()


def cut(path):
    """Cut up the final part of the path into CHUNK_SIZE chunks and concatenate them all together"""
    CHUNK_SIZE = 64
    chunks = []
    s = os.path.basename(path)
    for i in range(0, len(s), CHUNK_SIZE):
        chunks.insert(0, s[max(0, len(s) - i - CHUNK_SIZE) : len(s) - i])
    chunks.insert(0, os.path.dirname(path))
    return os.path.join(*chunks)


async def scrape_site(url, depth=0):
    if depth > MAX_DEPTH:
        return

    try:
        a = urlparse(url)
        valid = a.scheme and a.netloc
    except AttributeError:
        valid = False
    if not valid:
        print(f"Invalid URL: {url}")
        return

    filepath = os.path.normpath(os.path.join(OUTPUT_ROOT, a.netloc, a.path.lstrip("/")))
    if filepath in downloaded:
        print(f"Already downloaded: {url}")
        return

    try:
        retry_options = ExponentialRetry(attempts=5)
        retry_client = RetryClient(raise_for_status=False, retry_options=retry_options)
        # XXX: Disable verification of SSL is a security risk,
        # but some sites don't work for me if I don't do this
        async with retry_client.get(url, verify_ssl=False) as response:
            content_type = response.content_type.split("/")
            status = response.status
            if content_type[0] == "text":
                text = await response.text()
            else:
                content = await response.read()
    except aiohttp.ClientError as e:
        print(f'Client error "{e}": {url}')
        return
    except asyncio.TimeoutError as e:
        print(f'Timeout error "{e}": {url}')
        return
    except UnicodeDecodeError as e:
        print(f'Decode error "{e}": {url}')
        return
    finally:
        await retry_client.close()

    if status != 200:
        print(f"Failed {status}: {url}")
        return

    # Files with extremely long names were encountered, so they need to be shortened
    filepath = cut(filepath)
    # Some HTML pages were not give an explicit file name
    if content_type[1] == "html" and not (
        filepath.endswith(".html") or filepath.endswith(".htm")
    ):
        filepath = os.path.join(filepath, "index.html")

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if content_type[0] == "text":
        with open(filepath, "w") as file:
            file.write(text)
    else:
        with open(filepath, "wb") as file:
            file.write(content)
    downloaded.add(filepath)
    print(f"Downloaded: {url}")

    if content_type[1] == "html" and a.netloc.endswith("dukekunshan.edu.cn"):
        # Prevent accidentally DOSing the server
        await asyncio.sleep(random.randint(0, 3))

        soup = BeautifulSoup(text, "html.parser")
        links = soup.find_all("a", href=True)

        async with asyncio.TaskGroup() as tg:
            for link in links:
                href = link.get("href")
                # Make sure it's an absolute URL
                if href.startswith("/"):
                    absolute_url = urljoin(url, href)
                else:
                    absolute_url = href

                tg.create_task(scrape_site(absolute_url, depth + 1))
                # I cannot find a way to make HTTP to HTTPS redirects work, so I'll just try both
                if absolute_url.startswith("http://"):
                    tg.create_task(
                        scrape_site(
                            "https://" + absolute_url[len("http://") :], depth + 1
                        )
                    )


if __name__ == "__main__":
    asyncio.run(scrape_site("https://www.dukekunshan.edu.cn/"))
