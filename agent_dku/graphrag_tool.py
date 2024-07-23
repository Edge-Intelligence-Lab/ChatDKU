from graphrag.query.cli import _read_config_parameters
import pandas as pd
from pathlib import Path
from graphrag.query.indexer_adapters import (
    read_indexer_covariates,
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_reports,
    read_indexer_text_units,
)
from graphrag.query.factories import get_global_search_engine
import re




class GraphragTool():
    def __init__(self):
        ### init data,config
        self.data_dir = Path("/home/Glitterccc/projects/DKU_LLM/GraphDKU/output/20240715-182239/artifacts")
        self.root_dir = "/home/Glitterccc/projects/DKU_LLM/GraphDKU"
        self.config = _read_config_parameters(self.root_dir)
        self.community_level = 2
        self.response_type = "Multiple Paragraphs"
        
        self.final_nodes: pd.DataFrame = pd.read_parquet(
            self.data_dir / "create_final_nodes.parquet"
        )
        self.final_entities: pd.DataFrame = pd.read_parquet(
            self.data_dir / "create_final_entities.parquet"
        )
        self.final_community_reports: pd.DataFrame = pd.read_parquet(
            self.data_dir / "create_final_community_reports.parquet"
        )

        self.reports = read_indexer_reports(
            self.final_community_reports, self.final_nodes, self.community_level
        )
        self.entities = read_indexer_entities(self.final_nodes, self.final_entities, self.community_level)
        self.search_engine = get_global_search_engine(
            self.config,
            reports=self.reports,
            entities=self.entities,
            response_type=self.response_type,
        )
        print("-"*10+"graphrag_tool loaded"+"-"*10)
        
    def get_reports_and_entities(self, contexts_list):
        result_id = []
        full_context = ""
        for context in contexts_list:
            full_context += context

        numbers = re.findall(r'Data: Reports \((\d+.*?)\)', full_context)

        retrieved_report_id_list = []
        for number_set in numbers:
            retrieved_report_id_list.extend([int(num) for num in number_set.split(', ')])
            
        retrieved_reports = []
        entities_id_list = []
        for report in self.reports:
            if int(report.id) in retrieved_report_id_list:
                numbers = re.findall(r'Data: Entities \((\d+.*?)\)', report.full_content)
                for number_set in numbers:
                    for num in number_set.split(', '):
                        if int(num) not in entities_id_list:
                            entities_id_list.append(int(num))
                retrieved_reports.append(report)
        retrieved_entities = [list(self.final_entities['description'])[index] for index in entities_id_list]
        return retrieved_reports, retrieved_entities
        
        
    def global_query(self,query):
        search_result_list = self.search_engine.search_for_agent(query=query)
        high_score_responce_list = []
        contexts_list = []
        for response in search_result_list:
            if response.response[0]['score']>0: # type: ignore
                high_score_responce_list.append(response)
                for dict in response.response:
                    contexts_list.append(dict['answer']) # type: ignore

        retrieved_reports, retrieved_entities = self.get_reports_and_entities(contexts_list)
        return contexts_list, retrieved_reports, retrieved_entities
        
def main():
    graphragtool = GraphragTool()

    query="what do you know about DKU?"
    # graph_contexts, graph_full_conexts = ragtools.graph_global_tool(query)
    contexts_list, retrieved_reports, retrieved_entities = graphragtool.global_query(query)
    print(contexts_list)
    print('-'*20+'retrieved_reports'+'-'*20+'\n')
    print(retrieved_reports)
    
    
if __name__ == "__main__":
    main()