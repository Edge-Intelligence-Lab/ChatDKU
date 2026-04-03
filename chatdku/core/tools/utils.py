import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import contextmanager

import pandas as pd

from chatdku.config import config
from chatdku.core.tools.retriever.base_retriever import NodeWithScore


class QueryTimeoutError(Exception):
    """Raised when a query exceeds the timeout limit."""

    pass


@contextmanager
def timeout(seconds: int = 5):
    """
    Thread-safe timeout using concurrent.futures.

    This function is used as a wrapper context around functions to
    time their response. If there is no response in `seconds`,
    it will trigger `QueryTimeoutError`.

    Args:
        seconds (int): The amount of seconds it should take until \
        there is a `QueryTimeoutError`.

    """

    class TimeoutContext:
        def __init__(self):
            self.executor = ThreadPoolExecutor(max_workers=1)
            self.future = None

        def run(self, func, *args, **kwargs):
            self.future = self.executor.submit(func, *args, **kwargs)
            try:
                return self.future.result(timeout=seconds)
            except FuturesTimeoutError:
                raise QueryTimeoutError(f"Query exceeded {seconds} second timeout")
            finally:
                self.executor.shutdown(wait=False)

    ctx = TimeoutContext()
    try:
        yield ctx
    finally:
        if ctx.executor:
            ctx.executor.shutdown(wait=False)


def get_url(metadata: dict):
    """
    Get the URL of the document from the file_path.

    The URL is searched from the `config.url_csv_path` file.
    """
    df = pd.read_csv(config.url_csv_path)
    # Since `file_path` is the absolute path, we only want the part beginning with "dku_website"
    df["file_path_forweb"] = df["file_path"].str.extract(r"(dku_website/.*)")

    try:
        try:
            path = metadata["file_path"]
        except Exception:
            path = metadata["file_directory"] + "/" + metadata["filename"]

        if "dku_website" in path:
            match = re.search(r"dku_website/.*", path)
            if match:
                result = match.group(0)
                matching_row = df[df["file_path_forweb"] == result]
                if not matching_row.empty:
                    return matching_row.iloc[0]["url"]
        else:
            matching_row = df[df["file_path"] == path]
            if not matching_row.empty:
                return matching_row.iloc[0]["url"]
        return "no url"
    except Exception as e:
        return f"no url, error: {str(e)}"


def nodes_to_dicts(nodes: list[NodeWithScore]) -> list:
    """
    Convert nodes to a list of dictionaries.

    Args:
        nodes (list[NodeWithScore]): The nodes to convert.

    Returns:
        list: A list of dictionaries.
    """
    result = []
    for node in nodes:
        if isinstance(node, NodeWithScore):
            result.append([{"text": node.text, "metadata": node.metadata}])
        if isinstance(node, str):
            result.append(node)
    return result
