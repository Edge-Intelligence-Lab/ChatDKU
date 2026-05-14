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
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use the configured Qwen endpoint to write compact topic and cluster summaries",
    )
    parser.add_argument(
        "--use-llm-maintenance",
        action="store_true",
        help="Use the configured Qwen endpoint to review wiki structure, conflict signals, and interconnections",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_wiki(
        nodes_path=args.nodes_path,
        output_dir=args.output_dir,
        use_llm=args.use_llm,
        use_llm_maintenance=args.use_llm_maintenance,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
