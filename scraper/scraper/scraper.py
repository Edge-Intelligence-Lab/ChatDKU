#!/usr/bin/env python

import os
import asyncio
import aiohttp
import time
import datetime
import csv
import mechanicalsoup
import requests
from argparse import ArgumentParser
from contextlib import AsyncExitStack
from bs4 import BeautifulSoup
from yarl import URL
from dataclass_csv import DataclassWriter
from pathlib import Path
from http.cookiejar import CookieJar
from ChatDKU.scraper.scraper.utils import Status, DownloadInfo, print_summary
from ChatDKU.scraper.scraper.filter_llm import filter_page
import logging

logger = logging.getLogger("scrap_logger")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler("error_url.log")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "%(message)s"
)
file_handler.setFormatter(file_formatter)

error_handler = logging.FileHandler("error.log")
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter(
    "[%(levelname)s] %(message)s"
)
error_handler.setFormatter(error_formatter)

logger.addHandler(file_handler)
logger.addHandler(error_handler)

logger.info("----URL LOGS for Scrapper----")



# Store URLs that we already tried to download with `DownloadInfo` to prevent
# infinite loop and make it possible to restore download progress
# TODO: Add download restore
tried: dict[str, DownloadInfo] = {}

delay_lock = asyncio.Lock()


def saml_login(url: str | URL) -> CookieJar:
    """Login with SAML 2.0/Shibboleth-based SSO and return a cookiejar.
    More about Shibboleth: https://help.switch.ch/aai/demo/expert/
    NOTE: This is specific for Duke SSO, changes might be necessary for a standalone tool
    """

    s = requests.Session()
    browser = mechanicalsoup.StatefulBrowser(session=s)
    browser.open(url)
    browser.select_form('form[method="post"]')
    browser["j_username"] = saml_username
    browser["j_password"] = saml_password
    browser.submit_selected()

    # As MechanicalSoup does not use JavaScript, we have to post `SAMLResponse`
    # back to service provider manually.
    browser.select_form('form[method="post"]')
    browser.submit_selected()

    return browser.get_cookiejar()


async def get(
    session: aiohttp.ClientSession, url: URL
) -> tuple[URL, list[str], str, str] | tuple[URL, list[str], str, bytes] | None:
    # Prevent accidentally DOSing the server
    async with delay_lock:
        await asyncio.sleep(args.delay)

    try:
        async with AsyncExitStack() as stack:
            # XXX: Disable verification of SSL is a security risk,
            # but some sites don't work for me if I don't do this
            response = await stack.enter_async_context(
                session.get(url, verify_ssl=False, allow_redirects=True)
            )
            if response.status != 200:
                if args.verbose >= 1:
                    print(f"Failed {response.status}: {url}")
                return None

            if args.saml and response.url.host == "shib.oit.duke.edu":
                cookiejar = saml_login(url)
                session.cookie_jar.update_cookies(cookiejar)

                response = await stack.enter_async_context(
                    session.get(url, verify_ssl=False, allow_redirects=True)
                )
                if response.url.host == "shib.oit.duke.edu":
                    if args.verbose >= 1:
                        print(f"SAML login failed: {url}")
                    return None

            content_type = response.content_type.split("/")
            ty = content_type
            if ty[0] == "text":
                content = await response.text()
            else:
                content = await response.read()

            filename = None
            disposition = response.content_disposition
            if disposition:
                filename = disposition.filename

            return response.url, ty, filename, content
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
    """Cut up path parts into args.path_part_max_size chunks and concatenate them all together, excluding extension"""
    if not path:
        return ""

    prefix, ext = os.path.splitext(path)
    parts = os.path.normpath(prefix).split(os.path.sep)

    def cut_part(part: str):
        chunks = []
        for i in range(0, len(part), args.path_part_max_size):
            chunks.insert(
                0, part[max(0, len(part) - i - args.path_part_max_size) : len(part) - i]
            )

        # Handle the leading "/" of absolute path
        if not chunks:
            return "/"
        else:
            return os.path.join(*chunks)

    pieces = [cut_part(p) for p in parts]
    pieces[-1] += ext
    return os.path.join(*pieces)


def is_included(url: URL) -> bool:
    """Check if URL is included for scraping according to constraints such as domain rules."""

    # Include all URLs if neither constraints were specified
    if not (args.domains or args.subdomains_of):
        return True

    return (url.host in args.domains) or any(
        [url.host.endswith("." + d) for d in args.subdomains_of]
    )


async def scrape_site(
    task_group: asyncio.TaskGroup,
    session: aiohttp.ClientSession,
    url: str | URL,
    depth: int = 0,
    retry: int = 0,
) -> None:
    # Verify the URL
    valid = False
    try:
        if isinstance(url, str):
            url = URL(url)
        if url.scheme and url.host:
            valid = True
    except ValueError:
        pass

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
    canonical_url, ty, filename, content = result
    included = is_included(canonical_url)
    if not (
        args.external == "all"
        or (args.external == "html" and ty[1] == "html")
        or (args.external == "attachments" and ty[1] != "html")
        or included
    ):
        tried[url].status = Status.EXCLUDED
        if args.verbose >= 1:
            print(f"URL not included: {canonical_url}")
        return

    if not filename:
        if ty[1] == "html":
            # Some HTML pages were not give an explicit file name
            if not (
                canonical_url.path.endswith(".html")
                or canonical_url.path.endswith(".htm")
            ):
                filename = "index.html"
            else:
                filename = ""
        else:
            # If it is not a webpage, and no filename in `Content-Disposition` is
            # specified, then the query string might be necessary to distinguish
            # different files downloaded.
            filename = canonical_url.query_string or ""

    file_path = os.path.normpath(
        os.path.join(
            args.output_root,
            canonical_url.host,
            canonical_url.path.lstrip("/"),
            filename,
        )
    )

    # Paths with extremely long parts were encountered, so they need to be shortened
    file_path = cut(file_path)

    # Save the content
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    try:
        if ty[0] == "text" and ty[1] == "html":
            print(f"[LLM FILTER] about to evaluate {canonical_url}")
            if not await filter_page(content, str(canonical_url), args):
                tried[url].status = Status.EXCLUDED
                if args.verbose >= 1:
                    print(f"Filtered out by LLM: {canonical_url}")
                return
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
        else:
            with open(file_path, "wb") as file:
                file.write(content)
    except Exception as e:
        print(e)
        logger.info(f"{canonical_url}")
        logger.error(f"Failed to save file {file_path}: {e}")
    tried[url].status = Status.SUCCESS
    tried[url].canonical_url = canonical_url
    tried[url].file_path = file_path
    if args.verbose >= 1:
        print(f"Success: {url}")

    if depth < args.max_depth and ty[1] == "html" and included:
        soup = BeautifulSoup(content, "html.parser")
        links = soup.find_all("a", href=True)

        for link in links:
            try:
                href = URL(link.get("href"))
            except ValueError:
                if args.verbose >= 1:
                    print(f"Invalid URL: {href}")
                continue

            # Make sure it's an absolute URL
            if href.is_absolute():
                absolute_url = href
            else:
                absolute_url = url.join(href)

            task_group.create_task(
                scrape_site(task_group, session, absolute_url, depth + 1)
            )


def dump_info() -> None:
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

        dump_info()

def remove_empty_dirs(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if not dirnames and not filenames:
            try:
                Path(dirpath).rmdir()
                if args.verbose >= 1:
                    print(f"Removed empty directory: {dirpath}")
            except OSError:
                pass

async def main() -> None:
    headers = {"User-Agent": args.user_agent}
    timeout = aiohttp.ClientTimeout(
        total=args.total_timeout, connect=args.connection_timeout
    )
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
        default=3,
        help="Maximum depth of recursive website download.",
    )
    parser.add_argument(
        "-T",
        "--total-timeout",
        type=float,
        default=300,
        help="Timeout (seconds) of the entire request.",
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
        "-E",
        "--external",
        choices=["html", "attachments", "all", "none"],
        default="none",
        help="Scrape one level of websites linked to even if they are not in e.g. the domains to scrape.",
    )
    parser.add_argument(
        "-D", "--domains", nargs="*", type=str, default=[], help="Domains to scrape."
    )
    parser.add_argument(
        "-S",
        "--subdomains-of",
        nargs="*",
        type=str,
        default=[],
        help="Scrape the subdomains of the given domains.",
    )
    parser.add_argument(
        "-a",
        "--user-agent",
        type=str,
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    )
    parser.add_argument(
        "--path-part-max-size",
        type=int,
        # Max filename for ext4 is 255 bytes, also accounting for mult-byte chars and extension
        default=50,
        help="Maximum length of path part before it would be broken up.",
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
        help="Time (seconds) before printing the latest progress report and dumping download information file.",
    )
    parser.add_argument(
        "-i",
        "--download-info-file",
        type=Path,
        default=Path("./download_info.csv"),
        help="Location to store the download infomation file (in CSV format).",
    )
    parser.add_argument(
        "-s",
        "--saml",
        nargs=2,
        metavar=("saml_username", "saml_password"),
        help="Login with SAML 2.0/Shibboleth-based SSO (provide username and password)",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable LLM filtering of pages."
    )
    args = parser.parse_args()

    if args.saml:
        saml_username, saml_password = args.saml

    try:
        asyncio.run(main())
        print("----------------DOWNLOAD COMPLETED----------------")
    except KeyboardInterrupt:
        print("----------------DOWNLOAD INTERRUPTED----------------")

    print_summary(tried.values())
    
    dump_info()
    remove_empty_dirs(Path(args.output_root))
