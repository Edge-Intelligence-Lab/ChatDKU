class Config:
    def __init__(self, embedding_model_type="small"):

        # about settings.py
        self.embedding = f"BAAI/bge-m3"
        self.llm = "meta-llama/Meta-Llama-3-8B-Instruct"
        self.tei_url = "http://localhost:18080"
        self.llm_url = "http://localhost:8000/v1"

        # about load_and_index
        self.data_dir = "/opt/RAG_data"
        self.documents_path = "/opt/RAG_data/new_parser_documents.pkl"
        self.update = False

        # about query
        self.chroma_db = (
            f"/opt/chroma_dbs/bge_m3_chroma_db"
        )
        # self.nodes_path = f"./nodes/nodes_{str(embedding_model_type)}_bge.pkl"
        self.docstore_path = (
            f"/opt/docstores/bge_m3_chroma_db"
        )
