import os
from typing import Any, Mapping, Optional

import dotenv

dotenv.load_dotenv()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)

def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_path(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


class _WriteProtectedDict(dict):
    """
    A dict that raises on item assignment to discourage bypassing the Config API.
    Use Config.set / Config.update / attribute assignment instead.
    """

    def __setitem__(self, key, value):
        raise TypeError(
            "Direct mutation is disabled. Use Config.set(...) or attribute assignment."
        )  # noqa

    def update(self, *args, **kwargs):
        raise TypeError("Direct mutation is disabled. Use Config.update(...).")  # noqa


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            inst = super().__new__(cls)
            # initialize once
            object.__setattr__(inst, "_store", {})  # raw mutable store, private
            object.__setattr__(
                inst, "_frozen_view", _WriteProtectedDict()
            )  # read-only view
            inst._initialize_defaults()
            cls._instance = inst
        return cls._instance

    # Internal: initialize defaults once
    def _initialize_defaults(self):
        llm_api_key = _env("LLM_API_KEY")
        redis_host = _env("REDIS_HOST", "localhost")
        redis_password = _env("REDIS_PASSWORD")

        self._store.update(
            {
                # LLM
                "llm": _env("LLM_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507"),
                "llm_url": _env("LLM_BASE_URL", "http://localhost:18085/v1"),
                "llm_api_key": llm_api_key,
                "backup_llm": _env("LLM_BACKUP_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507"),
                "backup_llm_url": _env("LLM_BACKUP_BASE_URL", "http://localhost:18085/v1"),
                "llm_temperature": _env_float("LLM_TEMPERATURE", 0.7),
                "context_window": _env_int("LLM_CONTEXT_WINDOW", 32000),
                "response_type": _env("LLM_RESPONSE_TYPE", "Multiple Paragraphs"),
                # Embedding
                "embedding": _env("EMBEDDING_MODEL", "BAAI/bge-m3"),
                "tokenizer": _env(
                    "TOKENIZER_PATH",
                    "Qwen/Qwen3-8B",
                ),
                "tei_url": _env("TEI_URL", "http://localhost:8080"),
                # Reranker
                "reranker_top_n": _env_int("RERANKER_TOP_N", 5),
                "reranker_backup_top_n": _env_int(
                    "RERANKER_BACKUP_TOP_N", 10
                ),  # fallback to embedding scores
                "reranker_base_url": _env("RERANKER_BASE_URL", "http://localhost:6767"),
                "reranker_model": _env("RERANKER_MODEL", "Qwen/Qwen3-VL-Reranker-8B"),
                "reranker_api_key": _env("RERANKER_API_KEY"),
                # Data
                "data_dir": _env_path("DATA_DIR", "./data"),
                "documents_path": _env_path("DOCUMENTS_PATH", "./data/parsed.pkl"),
                "nodes_path": _env_path("NODES_PATH", "./data/nodes.json"),
                "pipeline_cache": _env_path("PIPELINE_CACHE_DIR", "./pipeline_cache"),
                "url_csv_path": _env_path("URL_CSV_PATH", "./data/url_database.csv"),
                # Redis
                "redis_host": redis_host,
                "redis_password": redis_password,
                "index_name": _env("REDIS_INDEX_NAME", "chatdku"),
                # Chroma
                "chroma_host": _env("CHROMA_HOST", "localhost"),
                "chroma_db_port": _env_int("CHROMA_DB_PORT", 8010),
                "chroma_collection": _env("CHROMA_COLLECTION", "chatdku_docs"),
                "user_uploads_collection": _env(
                    "USER_UPLOADS_COLLECTION", "user_uploads"
                ),
                # Graph
                "docstore_path": _env_path("DOCSTORE_PATH", "./data/docstore"),
                "graph_data_dir": _env_path("GRAPH_DATA_DIR", "./graph/artifacts"),
                "graph_root_dir": _env_path("GRAPH_ROOT_DIR", "./graph"),
                # MISC
                "module_root_dir": os.path.dirname(os.path.abspath(__file__)),
            }
        )
        # refresh read-only view
        self._refresh_view()

    def _refresh_view(self):
        # Rebuild the read-only mapping so callers can inspect without mutating.
        object.__setattr__(
            self, "_frozen_view", _WriteProtectedDict(self._store.copy())
        )

    # Attribute access

    def __getattr__(self, key: str) -> Any:
        # Called when normal attribute lookup fails
        if key in self._store:
            return self._store[key]
        raise AttributeError(f"{type(self).__name__} has no attribute '{key}'")

    def __setattr__(self, key: str, value: Any) -> None:
        # Allow internal attributes to be set normally
        if key in {"_store", "_frozen_view"}:
            return object.__setattr__(self, key, value)
        # Route public assignments into the store
        self._store[key] = value
        self._refresh_view()

    def __delattr__(self, key: str) -> None:
        if key in {"_store", "_frozen_view"}:
            return object.__delattr__(self, key)
        if key in self._store:
            del self._store[key]
            self._refresh_view()
        else:
            raise AttributeError(f"{type(self).__name__} has no attribute '{key}'")

    # Dict-like API (preferred for bulk ops)

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._refresh_view()

    def update(self, mapping: Mapping[str, Any] = None, **kwargs) -> None:
        if mapping:
            self._store.update(dict(mapping))
        if kwargs:
            self._store.update(kwargs)
        self._refresh_view()

    def as_dict(self) -> dict:
        # Return a shallow copy to prevent external mutation
        return dict(self._store)

    def view(self) -> Mapping[str, Any]:
        # Read-only mapping to inspect at runtime
        return self._frozen_view


# Singleton instance
config = Config()

# EXAMPLES:
# config.llm_temperature = 0.3
# config.set("index_name", "chat_dku_advising_v2")
# config.update({"backup_llm_url": "http://localhost:18083/v1"}, response_type="Concise")
# reading safely:
# temp = config.llm_temperature
# all_values = config.as_dict()
# read-only view (raises on mutation): ro = config.view()
