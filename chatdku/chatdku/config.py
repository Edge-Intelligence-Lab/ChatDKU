import os


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = {
                # about settings.py
                "embedding": "BAAI/bge-m3",
                "llm": "meta-llama/Meta-Llama-3.1-8B-Instruct",
                "tokenizer": "/datapool/tokenizers/Meta-Llama-3.1-8B-Instruct",
                "tei_url": "http://localhost:18080",
                "llm_url": "http://localhost:8001/v1",
                "context_window": 64000,
                # about load_and_index
                "data_dir": "/datapool/RAG_data",
                "documents_path": "/datapool/chatdku_student/validfile.pkl",
                "pipeline_cache": "./pipeline_cache",
                "csv_path": "/datapool/RAG_data_new_website/download_info.csv",  # Store URL info of dku websites
                "update": False,
                # about query
                "chroma_db": "/datapool/db_Chatdku_student",
                # "nodes_path": "./nodes/nodes_{str(embedding_model_type)}_bge.pkl",
                "docstore_path": "/datapool/docstores/bge_m3_docstore",
                # about graphrag
                "graph_data_dir": "/home/Glitterccc/projects/DKU_LLM/GraphDKU/output/20240715-182239/artifacts",
                "graph_root_dir": "/home/Glitterccc/projects/DKU_LLM/GraphDKU",
                "response_type": "Multiple Paragraphs",
                "module_root_dir": os.path.dirname(os.path.abspath(__file__)),
            }
        return cls._instance

    def __getattr__(self, key):
        if key in self._config:
            return self._config[key]
        else:
            return super.__getattr__(key)

    def __setattr__(self, key, value):
        # Treat changing internal attributes differently from changing settings
        if key in ["_config", "_instance"]:
            super().__setattr__(key, value)
        else:
            self._config[key] = value

    def __delattr__(self, key):
        if key in self._config:
            del self._config[key]
        else:
            super.__delattr__(key)


config = Config()
