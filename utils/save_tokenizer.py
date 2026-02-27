#!/usr/bin/env python3

import argparse
from pathlib import Path
from transformers import AutoTokenizer, AutoConfig


def main():
    parser = argparse.ArgumentParser(
        description="Save a Hugging Face model's tokenizer and config to a local path."
    )
    parser.add_argument("model", type=str, help="The model name to download.")
    parser.add_argument(
        "path",
        type=Path,
        help="The path where the tokenizer and config will be saved to.",
    )

    args = parser.parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    config = AutoConfig.from_pretrained(args.model)

    tokenizer.save_pretrained(str(args.path))
    config.save_pretrained(str(args.path))


if __name__ == "__main__":
    main()
