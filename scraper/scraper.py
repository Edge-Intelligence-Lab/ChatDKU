#!/usr/bin/env python

import os
import asyncio
import aiohttp
import time
import datetime
import csv
from argparse import ArgumentParser
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from utils import Status, DownloadInfo, print_summary
from pathlib import Path
from dataclass_csv import DataclassWriter

# Store URLs that we already tried to download with `DownloadInfo` to prevent
# infinite loop and make it possible to restore download progress
# TODO: Add download restore
tried: dict[str, DownloadInfo] = {}

delay_lock = asyncio.Lock()


async def get(
    session: aiohttp.ClientSession, url: str
) -> tuple[str, list[str], str] | tuple[str, list[str], bytes] | None:

    # Prevent accidentally DOSing the server
    async with delay_lock:
        await asyncio.sleep(args.delay)

    try:
        # XXX: Disable verification of SSL is a security risk,
        # but some sites don't work for me if I don't do this
        async with session.get(url, verify_ssl=False, allow_redirects=True) as response:
            if response.status != 200:
                if args.verbose >= 1:
                    print(f"Failed {response.status}: {url}")
                return None

            content_type = response.content_type.split("/")
            ty = content_type
            if ty[0] == "text":
                return str(response.url), ty, await response.text()
            else:
                return str(response.url), ty, await response.read()
    except aiohttp.ClientError as e:
        if args.verbose >= 1:
            print(f'Client error "{e}": {url}')
    except asyncio.TimeoutError as e:
        if args.verbose >= 1:
            print(
                f'Timeout error (likely to be aiohttp Client total timeout reached) "{e}": {url}'
            )
    except UnicodeDecodeError as e:
        if args.verbose >= 1:
            print(f'Decode error "{e}": {url}')
    except ValueError as e:
        # This link seems to have too many redirects and gives this error:
        # ""http://libraries.ucsd.edu/services/data-curation/data-management/dmp-samples.html""
        if args.verbose >= 1:
            print(
                f'Value error (likely to be a url with too many redirects) "{e}": {url}'
            )

    return None


def cut(path: str) -> str:
    """Cut up the final part of the path into args.filename_chunk_size chunks and concatenate them all together"""
    chunks = []
    s = os.path.basename(path)
    for i in range(0, len(s), args.filename_chunk_size):
        chunks.insert(0, s[max(0, len(s) - i - args.filename_chunk_size) : len(s) - i])
    chunks.insert(0, os.path.dirname(path))
    return os.path.join(*chunks)


async def scrape_site(
    task_group: asyncio.TaskGroup,
    session: aiohttp.ClientSession,
    url: str,
    depth: int = 0,
    retry: int = 0,
) -> None:
    # Verify the URL
    try:
        url_parts = urlparse(url)
        valid = url_parts.scheme and url_parts.netloc
    except AttributeError:
        valid = False
    if not valid:
        if args.verbose >= 1:
            print(f"Invalid URL: {url}")
        return

    if retry > 0:
        if args.verbose >= 1:
            print(f"Start retry {retry} of: {url}")
    else:
        if url in tried:
            if args.verbose >= 2:
                print(f"Already downloaded: {url}")
            return
        tried[url] = DownloadInfo(url, depth, Status.DOWNLOADING, None, None)

    # Fetch the URL
    result = await get(session, url)
    if result is None:
        # Add a retry scraping task after some delay with exponential backoff
        if retry < args.max_retry:
            await asyncio.sleep(args.base_retry_time * (2**retry))
            task_group.create_task(
                scrape_site(task_group, session, url, depth, retry + 1)
            )
        else:
            tried[url].status = Status.FAILED
        return
    canonical_url, ty, content = result

    file_path = os.path.normpath(
        os.path.join(args.output_root, url_parts.netloc, url_parts.path.lstrip("/"))
    )
    # Files with extremely long names were encountered, so they need to be shortened
    file_path = cut(file_path)
    # Some HTML pages were not give an explicit file name
    if ty[1] == "html" and not (
        file_path.endswith(".html") or file_path.endswith(".htm")
    ):
        file_path = os.path.join(file_path, "index.html")

    try:
        # Save the content
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if ty[0] == "text":
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
        else:
            with open(file_path, "wb") as file:
                file.write(content)

        tried[url].status = Status.SUCCESS
        tried[url].canonical_url = canonical_url
        tried[url].file_path = file_path
        if args.verbose >= 1:
            print(f"Success: {url}")

    except IsADirectoryError as e:
        # FIXME: Using the actual name of the downloaded file should fix this.
        # Example: "https://careerservices.dukekunshan.edu.cn/?jet_download=49a7db4410a67df67886e01b09f06fac1f42b3ff"
        if args.verbose >= 1:
            print(
                f'IsADirectoryError error (giving up this URL, this would be fixed in the future) "{e}": {url}'
            )
        return

    if (
        depth < args.max_depth
        and ty[1] == "html"
        and url_parts.netloc.endswith("dukekunshan.edu.cn")
    ):
        soup = BeautifulSoup(content, "html.parser")
        links = soup.find_all("a", href=True)

        for link in links:
            href = link.get("href")
            # Make sure it's an absolute URL
            if href.startswith("/"):
                absolute_url = urljoin(url, href)
            else:
                absolute_url = href

            task_group.create_task(
                scrape_site(task_group, session, absolute_url, depth + 1)
            )
            # I cannot find a way to make HTTP to HTTPS redirects work, so I'll just try both
            if absolute_url.startswith("http://"):
                task_group.create_task(
                    scrape_site(
                        task_group,
                        session,
                        "https://" + absolute_url[len("http://") :],
                        depth + 1,
                    )
                )


async def peroidic_report() -> None:
    async def done() -> bool:
        await asyncio.sleep(args.check_if_done_delay)
        for v in tried.values():
            if v.status == Status.DOWNLOADING:
                return False
        return True

    prev_time = time.time()
    while True:
        while time.time() - prev_time < args.progress_report_delay:
            if await done():
                return
        prev_time = time.time()

        ts = datetime.datetime.now().replace(microsecond=0).isoformat()
        print(f"----------------PROGRESS {ts}----------------")
        print_summary(tried.values())


async def main() -> None:
    headers = {"User-Agent": args.user_agent}
    timeout = aiohttp.ClientTimeout(connect=args.connection_timeout)
    # Enable `trust_env` so that environmental variables like `HTTP_PROXY`
    # would be used for proxy settings.
    async with aiohttp.ClientSession(
        headers=headers, timeout=timeout, trust_env=True
    ) as session:
        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(scrape_site(task_group, session, args.url))
            task_group.create_task(peroidic_report())


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "url",
        type=str,
        nargs="?",
        default="https://www.dukekunshan.edu.cn/",
        help="Root URL to start web scraping.",
    )
    parser.add_argument(
        "-o",
        "--output-root",
        type=str,
        default="dku_website",
        help="Root directory of the downloaded website.",
    )
    parser.add_argument(
        "-r",
        "--max-depth",
        type=int,
        default=5,
        help="Maximum depth of recursive website download.",
    )
    parser.add_argument(
        "-t",
        "--connection-timeout",
        type=float,
        default=30,
        help="Timeout (seconds) to establish connection.",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=1,
        help="Time (seconds) to wait between requests.",
    )
    parser.add_argument(
        "-b",
        "--base-retry-time",
        type=float,
        default=5,
        help="Time (seconds) to wait before retrying a failed request. It will be multiplied by a factor for subsequent retries.",
    )
    parser.add_argument(
        "-m",
        "--max-retry",
        type=int,
        default=5,
        help="Maximum number of times to retry a request before giving up.",
    )
    parser.add_argument(
        "-a",
        "--user-agent",
        type=str,
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    )
    parser.add_argument(
        "--filename-chunk-size",
        type=int,
        default=64,
        help="Maximum length of filename before it would be broken up.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity level. Currently supporting -v and -vv.",
    )
    parser.add_argument(
        "--check-if-done-delay",
        type=int,
        default=5,
        help="Time (seconds) before checking if downloading is done.",
    )
    parser.add_argument(
        "--progress-report-delay",
        type=int,
        default=30,
        help="Time (seconds) before printing the latest progress report.",
    )
    parser.add_argument(
        "-i",
        "--download-info-file",
        type=Path,
        default=Path("./download_info.csv"),
        help="Location to store the download infomation file (in CSV format).",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main())
        print("----------------DOWNLOAD COMPLETED----------------")
    except KeyboardInterrupt:
        print("----------------DOWNLOAD INTERRUPTED----------------")

    print_summary(tried.values())

    with open(args.download_info_file, "w") as f:
        # FIXME: I think dataclass_csv should take all iterables instead of just lists as input,
        # as I think the conversion via `list()` is unnecessary.
        #
        # FIXME: dataclass_csv's `DataclassReader` considers both nothing `field,,field`
        # and empty quotes `field,"",field` as `None`, which is inconsistent with the
        # implementation of the csv module.
        # Also see: https://stackoverflow.com/questions/11379300/csv-reader-behavior-with-none-and-empty-string

        w = DataclassWriter(
            f, list(tried.values()), DownloadInfo, quoting=csv.QUOTE_NONNUMERIC
        )
        w.write()
