import asyncio
import dspy
import json
import pandas as pd
import re
import tiktoken
import time


from dspy_common import custom_cot_rationale
from graphrag.query.cli import _read_config_parameters
from graphrag.query.context_builder.conversation_history import (
    ConversationHistory,
)
from graphrag.query.factories import get_llm
from graphrag.query.indexer_adapters import (
    read_indexer_entities,
    read_indexer_reports,
)
from graphrag.query.structured_search.global_search.community_context import (
    GlobalCommunityContext,
)
from graphrag.query.structured_search.global_search.search import GlobalSearch
from llamaindex_tools import DocumentSummarizer
from pathlib import Path
from pydantic import Field
from typing import Annotated
from typing import Any

from chatdku.config import config


def json_clean(response: str):
    match = re.search(r"\{.*\}", response, re.DOTALL)
    if match:
        return match.group(0)
    else:
        return "Error Json"


class AgentGlobalSearch(GlobalSearch):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def search_for_agent(
        self,
        query: str,
        conversation_history: ConversationHistory | None = None,
        **kwargs: Any,
    ):
        """Perform a global search synchronously."""
        return asyncio.run(self.asearch_for_agent(query, conversation_history))

    async def asearch_for_agent(
        self,
        query: str,
        conversation_history: ConversationHistory | None = None,
        **kwargs: Any,
    ):
        """
        Perform a global search.

        Global search mode includes two steps:

        - Step 1: Run parallel LLM calls on communities' short summaries to generate answer for each batch
        - Step 2: Combine the answers from step 2 to generate the final answer
        """
        # Step 1: Generate answers for each batch of community short summaries
        start_time = time.time()
        context_chunks, context_records = self.context_builder.build_context(
            conversation_history=conversation_history, **self.context_builder_params
        )

        if self.callbacks:
            for callback in self.callbacks:
                callback.on_map_response_start(context_chunks)  # type: ignore
        map_responses = await asyncio.gather(
            *[
                self._map_response_single_batch(
                    context_data=data, query=query, **self.map_llm_params
                )
                for data in context_chunks
            ]
        )

        return map_responses

    def parse_search_response(self, search_response: str) -> list[dict[str, Any]]:
        """Parse the search response json and return a list of key points.

        Parameters
        ----------
        search_response: str
            The search response json string

        Returns
        -------
        list[dict[str, Any]]
            A list of key points, each key point is a dictionary with "answer" and "score" keys
        """
        # print(search_response)
        search_response = json_clean(search_response)
        # print("clean"*20)
        # print(search_response)

        parsed_elements = json.loads(search_response)["points"]
        return [
            {
                "answer": element["description"],
                "score": int(element["score"]),
            }
            for element in parsed_elements
        ]


class GraphragTool(dspy.Module):
    def __init__(self):

        ### init data,config
        self.data_dir = Path(config.graph_data_dir)
        self.root_dir = config.graph_root_dir
        self.config = _read_config_parameters(self.root_dir)
        self.community_level = 2
        self.response_type = config.response_type

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
        self.entities = read_indexer_entities(
            self.final_nodes, self.final_entities, self.community_level
        )

        self.search_engine = self.get_search_engine()

        self.summarizer = DocumentSummarizer()

        print("-" * 10 + "graphrag_tool loaded" + "-" * 10)

    def get_reports_and_entities(self, contexts_list):
        full_context = ""
        for context in contexts_list:
            full_context += context

        numbers = re.findall(r"Data: Reports \((\d+.*?)\)", full_context)

        retrieved_report_id_list = []
        for number_set in numbers:
            retrieved_report_id_list.extend(
                [int(num) for num in number_set.split(", ")]
            )

        retrieved_reports = []
        entities_id_list = []
        for report in self.reports:
            if int(report.id) in retrieved_report_id_list:
                numbers = re.findall(
                    r"Data: Entities \((\d+.*?)\)", report.full_content
                )
                for number_set in numbers:
                    for num in number_set.split(", "):
                        if int(num) not in entities_id_list:
                            entities_id_list.append(int(num))
                retrieved_reports.append(report)
        # find entities from context
        numbers = re.findall(r"Data: Entities \((\d+.*?)\)", full_context)
        for number_set in numbers:
            entities_id_list.extend([int(num) for num in number_set.split(", ")])
        # print(entities_id_list)
        retrieved_entities = []
        for index in range(0, len(list(self.final_entities["description"]))):
            if index in entities_id_list:
                tmp_dic = {}
                tmp_dic["entity_id"] = index
                tmp_dic["content"] = list(self.final_entities["description"])[index]
                retrieved_entities.append(tmp_dic)

        # retrieved_entities = [list(self.final_entities['description'])[index] for index in entities_id_list]
        return retrieved_reports, retrieved_entities

    def get_search_engine(self):
        token_encoder = tiktoken.get_encoding(self.config.encoding_model)
        gs_config = self.config.global_search
        return AgentGlobalSearch(
            llm=get_llm(self.config),
            context_builder=GlobalCommunityContext(
                community_reports=self.reports,
                entities=self.entities,
                token_encoder=token_encoder,
            ),
            token_encoder=token_encoder,
            max_data_tokens=gs_config.data_max_tokens,
            map_llm_params={
                "max_tokens": gs_config.map_max_tokens,
                "temperature": 0.0,
            },
            reduce_llm_params={
                "max_tokens": gs_config.reduce_max_tokens,
                "temperature": 0.0,
            },
            allow_general_knowledge=False,
            json_mode=False,
            context_builder_params={
                "use_community_summary": False,
                "shuffle_data": True,
                "include_community_rank": True,
                "min_community_rank": 0,
                "community_rank_name": "rank",
                "include_community_weight": True,
                "community_weight_name": "occurrence weight",
                "normalize_community_weight": True,
                "max_tokens": gs_config.max_tokens,
                "context_name": "Reports",
            },
            concurrent_coroutines=gs_config.concurrency,
            response_type=self.response_type,
        )

    def global_query(self, query):
        search_result_list = self.search_engine.search_for_agent(query=query)
        high_score_responce_list = []
        contexts_list = []
        for response in search_result_list:
            if response.response[0]["score"] > 0:  # type: ignore
                high_score_responce_list.append(response)
                for dict in response.response:
                    contexts_list.append(dict["answer"])  # type: ignore

        retrieved_reports, retrieved_entities = self.get_reports_and_entities(
            contexts_list
        )
        return contexts_list, retrieved_reports, retrieved_entities

    def forward(
        self,
        query: Annotated[
            str,
            Field(
                description="Texts that might be semantically similar to the real answer to the question."
            ),
        ],
    ):
        contexts_list, retrieved_reports, retrieved_entities = self.global_query(query)
        return contexts_list
        # return dspy.Prediction(
        #     result=self.summarizer(documents=contexts_list, query=query).summary
        # )


def main():
    graphragtool = GraphragTool()

    query = "what do you know about DKU club?"
    # graph_contexts, graph_full_conexts = ragtools.graph_global_tool(query)
    contexts_list, retrieved_reports, retrieved_entities = graphragtool.global_query(
        query
    )
    # print(contexts_list)
    print("-" * 20 + "retrieved_reports" + "-" * 20 + "\n")
    print(retrieved_reports)
    print("-" * 20 + "retrieved_entities" + "-" * 20 + "\n")
    print(retrieved_entities)


if __name__ == "__main__":
    main()
