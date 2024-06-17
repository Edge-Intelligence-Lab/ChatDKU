#!/usr/bin/env python3

import pickle
from argparse import ArgumentParser
from utils import print_summary


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("filename", type=str)
    parser.add_argument(
        "-s",
        "--summary",
        action="store_true",
        help="Print summary such as the total number of success/failed downloads.",
    )
    args = parser.parse_args()

    # XXX: Note that pickle format would allow arbitrary code execution
    with open(args.filename, "rb") as file:
        info = pickle.load(file)

    if args.summary:
        print_summary(info)

    else:
        print("url,depth,status")
        for url, i in info.items():
            print(f'"{url}",{i.depth},{i.status}')


if __name__ == "__main__":
    main()
