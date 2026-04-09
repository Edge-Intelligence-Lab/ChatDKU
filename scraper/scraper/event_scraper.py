#!/usr/bin/env python3

import argparse
import asyncio
import os
import sys
from argparse import Namespace
from pathlib import Path

import aiohttp
from yarl import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scraper as s
from chatdku.config import config

DEFAULT_LINKS = [
    "https://calendar.dukekunshan.edu.cn/events?page=0",
    "https://calendar.dukekunshan.edu.cn/events?page=1",
    "https://calendar.dukekunshan.edu.cn/events?page=2",
    "https://calendar.dukekunshan.edu.cn/events?page=3",
    "https://calendar.dukekunshan.edu.cn/events?page=4",
    "https://calendar.dukekunshan.edu.cn/events?page=5",
    "https://calendar.dukekunshan.edu.cn/events?page=6",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape DKU event pages without query-string collisions."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(config.event_homepage_path),
        help="Base output directory. Each event page is written to its own subdirectory.",
    )
    parser.add_argument(
        "--download-info-dir",
        type=Path,
        default=None,
        help="Directory for per-page download_info CSV files. Defaults to output root.",
    )
    parser.add_argument(
        "--saml-username",
        type=str,
        default=os.getenv("NETID"),
        help="NETID username. Defaults to env var NETID.",
    )
    parser.add_argument(
        "--saml-password",
        type=str,
        default=os.getenv("NETID_PASSWORD"),
        help="NETID password. Defaults to env var NETID_PASSWORD.",
    )
    parser.add_argument(
        "--verbose",
        action="count",
        default=1,
        help="Verbosity level passed to the scraper.",
    )
    return parser.parse_args()


def get_page_tag(url: str, index: int) -> str:
    page = URL(url).query.get("page")
    return f"page_{page}" if page is not None else f"page_{index}"


def configure_scraper(args, links: list[str]):
    download_info_dir = args.download_info_dir or args.output_root
    s.args = Namespace(
        url=links[0],
        output_root=str(args.output_root),
        max_depth=0,
        total_timeout=300,
        connection_timeout=30,
        delay=1,
        base_retry_time=5,
        max_retry=5,
        external="none",
        domains=["calendar.dukekunshan.edu.cn", "shib.oit.duke.edu"],
        subdomains_of=[],
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        path_part_max_size=50,
        verbose=args.verbose,
        check_if_done_delay=5,
        progress_report_delay=30,
        download_info_file=download_info_dir / "download_info.csv",
        saml=(
            (args.saml_username, args.saml_password)
            if args.saml_username and args.saml_password
            else None
        ),
        use_llm=False,
    )

    if s.args.saml:
        s.saml_username, s.saml_password = s.args.saml


async def scrape_one(url: str, index: int, output_root: Path, download_info_dir: Path):
    page_tag = get_page_tag(url, index)
    page_output_root = output_root / page_tag
    s.args.url = url
    s.args.output_root = str(page_output_root)
    s.args.download_info_file = download_info_dir / f"download_info_{page_tag}.csv"
    s.tried.clear()

    headers = {"User-Agent": s.args.user_agent}
    timeout = aiohttp.ClientTimeout(
        total=s.args.total_timeout,
        connect=s.args.connection_timeout,
    )
    async with aiohttp.ClientSession(
        headers=headers,
        timeout=timeout,
        trust_env=True,
    ) as session:
        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(s.scrape_site(task_group, session, URL(url), depth=0))

    s.remove_empty_dirs(page_output_root)
    return dict(s.tried)


async def main():
    args = parse_args()
    links = DEFAULT_LINKS
    download_info_dir = args.download_info_dir or args.output_root
    download_info_dir.mkdir(parents=True, exist_ok=True)
    args.output_root.mkdir(parents=True, exist_ok=True)
    configure_scraper(args, links)
    all_tried = {}

    for index, url in enumerate(links):
        all_tried.update(await scrape_one(url, index, args.output_root, download_info_dir))

    s.tried.clear()
    s.tried.update(all_tried)
    s.args.download_info_file = download_info_dir / "download_info.csv"
    s.dump_info()


if __name__ == "__main__":
    asyncio.run(main())
