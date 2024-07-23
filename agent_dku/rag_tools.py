from llamaindex_tool import LlamaindexTool
from graphrag_tool import GraphragTool

class RagTools():
    def __init__(self):
        self.llamaindex_tool = LlamaindexTool()
        self.graphrag_tool = GraphragTool()
        
    ### llamaindex tool
    def tool1(self, query, retriever):
        return self.llamaindex_tool.query(query,retriever)
    
    def tool2(self, query):
        ### some bugs
        return self.graphrag_tool.global_query(query)
        
        