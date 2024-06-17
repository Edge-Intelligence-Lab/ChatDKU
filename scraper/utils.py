from enum import Enum
from dataclasses import dataclass


class Status(Enum):
    DOWNLOADING = 0
    SUCCESS = 1
    FAILED = 2

    def __str__(self):
        return self.name


@dataclass
class DownloadInfo:
    depth: int
    status: Status


def print_summary(info: dict[str, DownloadInfo]) -> None:
    cnt = {}
    for v in info.values():
        cnt[v.status] = cnt.get(v.status, 0) + 1
    for k, v in cnt.items():
        print(f"{str(k) + ':': <20}{v}")
    print(f"{'TOTAL:': <20}{sum(cnt.values())}")
