from enum import StrEnum
from dataclasses import dataclass
from typing import Iterable, Optional


class Status(StrEnum):
    DOWNLOADING = "downloading"
    SUCCESS = "success"
    FAILED = "failed"
    EXCLUDED = "excluded"


@dataclass
class DownloadInfo:
    url: str
    depth: int
    status: Status
    # The target URL after following the redirects, or the original URL if there are no redirects.
    # `None` if download has not succeeded.
    canonical_url: Optional[str] = None
    # Path to the downloaded file.
    # `None` if download has not succeeded.
    file_path: Optional[str] = None


def print_summary(info: Iterable[DownloadInfo]) -> None:
    cnt = {}
    for v in info:
        cnt[v.status] = cnt.get(v.status, 0) + 1
    for k, v in cnt.items():
        print(f"{str(k) + ':': <20}{v}")
    print(f"{'TOTAL:': <20}{sum(cnt.values())}")
