#!/usr/bin/env python3

import os
from pathlib import Path
import pickle
import chromadb
from settings import setup
from update_data import update_data, hash_directory, update_sub_data


from settings import Config

config = Config()


def load_data(
    data_dir: str,
):
    documents = update_data(data_dir)

    print("Data loading done")




def main():
    setup(add_system_prompt=True)
    config = Config()

    load_data(
        data_dir=str(config.data_dir),
    )


if __name__ == "__main__":
    main()
