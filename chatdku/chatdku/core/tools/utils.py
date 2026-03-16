import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from time import perf_counter

import pandas as pd

from chatdku.config import config
from chatdku.core.tools.retriever.base_retriever import NodeWithScore

# Reuse a single executor to avoid creating unbounded threads under load.
# Keep workers modest; tune if needed.
_EXECUTOR = ThreadPoolExecutor(max_workers=8)

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
            self.future = None

        def run(self, func, *args, **kwargs):
            t_submit = perf_counter()

            def _wrapper():
                t_start = perf_counter()
                wait = t_start - t_submit

                if wait > 0.5:
                    print(f"[timeout] queued_for={wait:.3f}s func={getattr(func, '__name__', type(func).__name__)}")
                return func(*args, **kwargs)

            self.future = _EXECUTOR.submit(_wrapper)
            try:
                return self.future.result(timeout=seconds)
            except FuturesTimeoutError:
                # Best-effort cancellation (only cancels if not started)
                if self.future is not None:
                    self.future.cancel()                
                raise QueryTimeoutError(f"Query exceeded {seconds} second timeout")

    ctx = TimeoutContext()
    yield ctx


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
