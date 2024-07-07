class Config:
    def __init__(self, embedding_model_type="small"):

        # about settings.py
        self.embedding = f"BAAI/bge-{str(embedding_model_type)}-en-v1.5"
        self.llm = "meta-llama/Meta-Llama-3-8B-Instruct"
        self.ollama_url = "http://localhost:11434"
        self.llm_url = "http://localhost:8000/v1"
        
        # about load_and_index
        self.data_dir = "/home/Glitterccc/projects/DKU_LLM/RAG_data"
        self.documents_path = "eng_documents.pkl"
        self.update = False

        # about query
        self.chroma_db = f"./chroma_dbs/eng_{str(embedding_model_type)}_bge_chroma_db"
        self.nodes_path = f"./nodes/nodes_{str(embedding_model_type)}_bge.pkl"
        self.docstore_path = f"./docstores/eng_{str(embedding_model_type)}_bge_docstore"
        


