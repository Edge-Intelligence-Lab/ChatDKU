from enum import StrEnum
from dataclasses import dataclass
from typing import Iterable


class Status(StrEnum):
    DOWNLOADING = "downloading"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class DownloadInfo:
    url: str
    depth: int
    status: Status


def print_summary(info: Iterable[DownloadInfo]) -> None:
    cnt = {}
    for v in info:
        cnt[v.status] = cnt.get(v.status, 0) + 1
    for k, v in cnt.items():
        print(f"{str(k) + ':': <20}{v}")
    print(f"{'TOTAL:': <20}{sum(cnt.values())}")
