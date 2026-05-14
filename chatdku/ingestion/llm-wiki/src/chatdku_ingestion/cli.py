from __future__ import annotations

import argparse
import json

from chatdku.config import config

from .builder import build_wiki


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build ChatDKU wiki pages from normalized nodes.json"
    )
    parser.add_argument(
        "--nodes-path",
        default=config.nodes_path,
        help="Path to nodes.json from existing ingestion pipeline",
    )
    parser.add_argument(
        "--output-dir",
        default=config.wiki_path,
        help="Output root for wiki/ and graph/ folders",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_wiki(nodes_path=args.nodes_path, output_dir=args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
