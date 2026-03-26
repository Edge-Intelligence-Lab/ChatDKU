import os
from typing import Any, Mapping, Optional
from urllib.parse import quote_plus

import dotenv

dotenv.load_dotenv()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


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
        redis_host = _env("REDIS_HOST")
        redis_password = _env("REDIS_PASSWORD")
        llamaparse_api = _env("LLAMAPARSE_API")
        SQLALCHEMY_DATABASE_URI = "postgresql://{}:{}@{}:{}/{}".format(
            os.environ.get("DB_USER", "chatdku_readonly"),
            quote_plus(os.environ.get("DB_PASSWORD", "alohomora")),
            os.environ.get("DB_HOST", "localhost"),
            os.environ.get("DB_PORT", "5432"),
            os.environ.get("DB_NAME", "chatdku_db"),
        )

        self._store.update(
            {
                # LLM
                "llm": "Qwen/Qwen3-30B-A3B-Instruct-2507",
                "llm_url": "http://localhost:18085/v1",
                "llm_api_key": llm_api_key,
                "backup_llm": "Qwen/Qwen3-30B-A3B-Instruct-2507",
                "backup_llm_url": "http://localhost:18085/v1",
                "llm_temperature": 0.7,
                "context_window": 32000,
                "response_type": "Multiple Paragraphs",
                # Embedding
                "embedding": "BAAI/bge-m3",
                "tokenizer": "/datapool/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",  # noqa E501
                "tei_url": "http://localhost:18080",
                "chunk_size": 512,
                "chunk_overlap": 40,
                # Reranker
                "reranker_top_n": 5,
                "reranker_backup_top_n": 10,  # If reranker fails, use the top n results using the embedding scores
                "reranker_base_url": "http://localhost:6767",
                "reranker_model": "Qwen/Qwen3-VL-Reranker-8B",
                "reranker_api_key": None,
                # Data
                "data_dir": "/datapool/chat_dku_public",
                "documents_path": "/datapool/chat_dku_public/parsed.pkl",  # This is Deprecated use nodes instead
                "nodes_path": "/datapool/chat_dku_public/nodes.json",
                "pipeline_cache": "./pipeline_cache",
                "url_csv_path": "/datapool/url_csv/url_database.csv",
                "event_path": "/datapool/chat_dku_public/event_data",
                # Redis
                "redis_host": redis_host,
                "redis_port": 6379,
                "redis_password": redis_password,
                "index_name": "chat_dku_public",
                # Chroma
                "chroma_db_port": 12400,
                "chroma_collection": "dku_public",
                "user_uploads_collection": "user_uploads",
                # PSQL
                "psql_uri": SQLALCHEMY_DATABASE_URI,
                # MISC
                "docstore_path": "/datapool/docstores/bge_m3_docstore",
                "graph_data_dir": "/home/Glitterccc/projects/DKU_LLM/GraphDKU/output/20240715-182239/artifacts",
                "graph_root_dir": "/home/Glitterccc/projects/DKU_LLM/GraphDKU",
                "llamaparse_api": llamaparse_api,
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
