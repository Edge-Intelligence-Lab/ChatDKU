#!/usr/bin/env python3

from llama_index.core import (
    VectorStoreIndex,
    get_response_synthesizer,
    Settings,
    PromptTemplate,
)
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever, TransformRetriever
from llama_index.core.response_synthesizers import ResponseMode
from llama_index.core.tools import QueryEngineTool, BaseTool, ToolMetadata
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.agent.react.types import (
    ActionReasoningStep,
    ObservationReasoningStep,
    ResponseReasoningStep,
)
from llama_index.core.agent import (
    Task,
    AgentChatResponse,
    ReActChatFormatter,
    QueryPipelineAgentWorker,
)
from llama_index.core.query_pipeline import (
    QueryPipeline,
    AgentInputComponent,
    AgentFnComponent,
    CustomAgentComponent,
    QueryComponent,
    ToolRunnerComponent,
    InputComponent,
    Link,
)
from llama_index.core.llms import (
    MessageRole,
    ChatMessage,
    ChatResponse,
    CompletionResponse,
)
from llama_index.llms.openai import OpenAI
from llama_index.core.agent.react.output_parser import ReActOutputParser
from llama_index.core.callbacks import CallbackManager
from typing import Dict, Any, Optional, Tuple, List, cast, Set, Optional
import phoenix as px
from llama_index.core.callbacks.global_handlers import set_global_handler
from settings import setup

# Override the fucking Llamaindex code
import llama_index.core.base.query_pipeline.query
from custom_query import validate_and_convert_stringable

llama_index.core.base.query_pipeline.query.validate_and_convert_stringable = (
    validate_and_convert_stringable
)


# When generating similar queries, the LLM is supposed to ONLY generate the
# queries themselves, one on each line. However, the LLM sometimes says things
# like `Here are n queries:` on the first line. This prompt used to explictly
# discourage this kind of output.
QUERY_GEN_PROMPT = (
    "You are a helpful assistant that generates multiple search queries based on a "
    "single input query. Do not output any additional information such as 'here are n queries'. "
    "Generate {num_queries} search queries, one on each line, related to the following input query:\n"
    "Query: {query}\n"
)

tool = None

# Maximum iteration of the agent
MAX_ITER = 3


def get_pipeline(
    retriever_type: str = "fusion",
    hyde: bool = True,
    vector_top_k: int = 5,
    bm25_top_k: int = 5,
    fusion_top_k: int = 5,
    num_queries: int = 2,
    synthesize_response: bool = True,
    response_mode: ResponseMode = ResponseMode.COMPACT,
) -> QueryPipeline:
    """
    Constructs a RAG query pipeline.

    Args:
        retriever_type: Type of retriever to use. Supported values are `vector` and `fusion`.
        hyde: If `True`, first use HyDE (Hypothetical Document Embeddings) to transform the query string before retrieval.
        vector_top_k: Top k similar nodes to retrieve using vector retriever (they are the inputs to fusion retriever if used).
        bm25_top_k: Top k similar nodes to retrieve using BM25 retriever (they are the inputs to fusion retriever if used).
        fusion_top_k: Top k similar documents to retrieve using fusion retriever.
        num_queries: Number of queries to generate for fusion retriever.
        synthesize_response: Synthesize responses using LLM if `True`, or output a list of nodes retrived if `False`.
        response_mode: Mode of response synthesis, see `llama_index.core.response_synthesizers.ResponseMode` for more details.

    Returns:
        A query pipeline that could be executed by supplying input to its `run()` method.

    Raises:
        ValueError: If an unsupported or invalid parameters are provided.
    """

    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("dku_html_pdf")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    vector_retriever = index.as_retriever(similarity_top_k=vector_top_k)

    if retriever_type == "vector":
        retriever = vector_retriever

    elif retriever_type == "fusion":
        docstore = SimpleDocumentStore.from_persist_path("./docstore")
        bm25_retriever = BM25Retriever.from_defaults(
            docstore=docstore, similarity_top_k=bm25_top_k
        )

        # NOTE: I am not sure why, but when using this retriever you MUST supply an LLM,
        # otherwise errors will be reported at the synthesizer stage. While this might
        # be due to the need of using an LLM at the query generation stage, it still
        # won't work if you set num_queries=1.
        retriever = QueryFusionRetriever(
            [vector_retriever, bm25_retriever],
            similarity_top_k=fusion_top_k,
            num_queries=num_queries,
            query_gen_prompt=QUERY_GEN_PROMPT,
            use_async=True,
            verbose=True,
        )

    else:
        raise ValueError(f"Unsupported retriever_type: {retriever_type}")

    if hyde:
        # NOTE: `HyDEQueryTransform` would effectively not work if used as an
        # component of the query pipeline by itself, since it returns a `QueryBundle`
        # with custom embedding strings that would be dropped when passed down the
        # pipeline as only the `query_str` attribute would be sent to the next
        # component.
        retriever = TransformRetriever(
            retriever=retriever,
            query_transform=HyDEQueryTransform(include_original=True),
        )

    query_engine = RetrieverQueryEngine(
        retriever=retriever, response_synthesizer=get_response_synthesizer()
    )

    global tool
    tool = QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name="tool",
        description=(
            "Useful for querying the website of Duke Kunshan University (DKU) and other publicly available documents of DKU"
        ),
    )

    ## Agent Input Component
    ## This is the component that produces agent inputs to the rest of the components
    ## Can also put initialization logic here.
    def agent_input_fn(task: Task, state: Dict[str, Any]) -> Dict[str, Any]:
        """Agent input function.

        Returns:
            A Dictionary of output keys and values. If you are specifying
            src_key when defining links between this component and other
            components, make sure the src_key matches the specified output_key.

        """
        # initialize current_reasoning
        if "current_reasoning" not in state:
            state["current_reasoning"] = []
            state["count"] = 0
        reasoning_step = ObservationReasoningStep(observation=task.input)
        state["current_reasoning"].append(reasoning_step)
        convo_history_str = "\n".join(state["convo_history"]) or "None"
        return {"input": task.input, "convo_history": convo_history_str}

    agent_input_component = AgentInputComponent(fn=agent_input_fn)

    retry_prompt_str = """\
    You are trying to generate a proper natural language query given a user input.

    This query will then be interpreted by a downstream text-to-SQL agent which
    will convert the query to a SQL statement. If the agent triggers an error,
    then that will be reflected in the current conversation history (see below).

    If the conversation history is None, use the user input. If its not None,
    generate a new SQL query that avoids the problems of the previous SQL query.

    Input: {input}
    Convo history (failed attempts): 
    {convo_history}

    New input: """
    retry_prompt = PromptTemplate(retry_prompt_str)

    from llama_index.core import Response
    from typing import Tuple

    validate_prompt_str = """\
    Given the user query, validate whether the inferred SQL query and response from executing the query is correct and answers the query.

    Answer with YES or NO.

    Query: {input}
    Inferred SQL query: {sql_query}
    SQL Response: {sql_response}

    Result: """
    validate_prompt = PromptTemplate(validate_prompt_str)

    MAX_ITER = 3

    def agent_output_fn(
        task: Task, state: Dict[str, Any], output: Response
    ) -> Tuple[AgentChatResponse, bool]:
        """Agent output component."""
        print(f"> Inferred SQL Query: {output.metadata['sql_query']}")
        print(f"> SQL Response: {str(output)}")
        state["convo_history"].append(
            f"Assistant (inferred SQL query): {output.metadata['sql_query']}"
        )
        state["convo_history"].append(f"Assistant (response): {str(output)}")

        # run a mini chain to get response
        validate_prompt_partial = validate_prompt.as_query_component(
            partial={
                "sql_query": output.metadata["sql_query"],
                "sql_response": str(output),
            }
        )
        qp = QueryPipeline(chain=[validate_prompt_partial, Settings.llm])
        validate_output = qp.run(input=task.input)

        state["count"] += 1
        is_done = False
        if state["count"] >= MAX_ITER:
            is_done = True
        if "YES" in validate_output.message.content:
            is_done = True

        return AgentChatResponse(response=str(output)), is_done

    agent_output_component = AgentFnComponent(fn=agent_output_fn)

    pipeline = QueryPipeline(verbose=True)
    pipeline.add_modules(
        {
            "input": agent_input_component,
            "retry_prompt": retry_prompt,
            "llm": Settings.llm,
            "query_engine": query_engine,
            "output_component": agent_output_component,
        }
    )

    pipeline.add_link("input", "retry_prompt", src_key="input", dest_key="input")
    pipeline.add_link(
        "input", "retry_prompt", src_key="convo_history", dest_key="convo_history"
    )
    pipeline.add_chain(["retry_prompt", "llm", "query_engine", "output_component"])

    return pipeline


def main():
    setup(add_system_prompt=True)

    px.launch_app()
    set_global_handler("arize_phoenix")

    pipeline = get_pipeline(
        retriever_type="fusion",
        hyde=True,
        vector_top_k=5,
        bm25_top_k=5,
        fusion_top_k=5,
        num_queries=3,
        synthesize_response=True,
        response_mode=ResponseMode.COMPACT,
    )

    # import networkx
    # import matplotlib
    # import matplotlib.pyplot as plt

    # fig = plt.figure()
    # networkx.draw(pipeline.clean_dag)
    # matplotlib.use("Agg")
    # fig.savefig("pipeline.png")

    agent_worker = QueryPipelineAgentWorker(pipeline)
    agent = agent_worker.as_agent(callback_manager=CallbackManager([]), verbose=True)
    agent.reset()

    while True:
        try:
            print("*" * 32)
            query = input("> ")
            output = agent.chat(query)
            print("+" * 32)
            print(str(output))
        except EOFError:
            break
        except:
            print("FAILED")


if __name__ == "__main__":
    main()
