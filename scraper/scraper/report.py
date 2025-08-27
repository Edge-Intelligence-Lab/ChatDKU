#!/usr/bin/env python3

from argparse import ArgumentParser
from utils import DownloadInfo, print_summary
from pathlib import Path
from dataclass_csv import DataclassReader


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument(
        "filename", type=Path, nargs="?", default=Path("./download_info.csv")
    )
    args = parser.parse_args()

    # XXX: Note that pickle format would allow arbitrary code execution
    with open(args.filename, "r") as f:
        reader = DataclassReader(f, DownloadInfo)
        print_summary(reader)


if __name__ == "__main__":
    main()
