from rag_tools import RagTools

class Memory():
    def __init__(self):
        self.contexts = []
        self.llamaindex_nodes = []
        self.graphrag_reports = []
        self.graphrag_entities = []
        




def main():
    rag_tools = RagTools()
    memory = Memory()
    
    #### get query from user
    query = "What do you know about dku?"
    
    #### if choose llamaindex with fusion retriever
    contexts, reranked_nodes = rag_tools.llamaindex_tool.query(query,retriever="fusion")
    memory.contexts.extend(contexts)
    memory.llamaindex_nodes.extend(reranked_nodes)
    
    #### if choose graphrag
    contexts_list, retrieved_reports, retrieved_entities = rag_tools.graphrag_tool.global_query(query)
    memory.contexts.extend(contexts_list)
    memory.graphrag_reports.extend(retrieved_reports)
    memory.graphrag_entities.extend(retrieved_entities)
    
    print(memory.contexts)
    print(memory.graphrag_reports)
    
        
        
    
    

if __name__ == "__main__":
    main()