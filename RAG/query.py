#!/usr/bin/env python3

from llama_index.core import VectorStoreIndex, get_response_synthesizer, Settings
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
from settings import parse_args_and_setup


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

    query_engine = RetrieverQueryEngine(retriever)

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
        reasoning_step = ObservationReasoningStep(observation=task.input)
        state["current_reasoning"].append(reasoning_step)
        return {"input": task.input}

    agent_input_component = AgentInputComponent(fn=agent_input_fn)

    # define prompt function
    def react_prompt_fn(
        task: Task, state: Dict[str, Any], input: str, tools: List[BaseTool]
    ) -> List[ChatMessage]:
        # Add input to reasoning
        chat_formatter = ReActChatFormatter()
        return chat_formatter.format(
            tools,
            chat_history=task.memory.get() + state["memory"].get_all(),
            current_reasoning=state["current_reasoning"],
        )

    react_prompt_component = AgentFnComponent(
        fn=react_prompt_fn, partial_dict={"tools": [tool]}
    )

    def parse_react_output_fn(
        task: Task, state: Dict[str, Any], chat_response: ChatResponse
    ):
        """Parse ReAct output into a reasoning step."""
        output_parser = ReActOutputParser()
        # if isinstance(chat_response, CompletionResponse):
        #     reasoning_step = output_parser.parse(chat_response.text)
        # else:
        reasoning_step = output_parser.parse(chat_response.message.content)
        return {"done": reasoning_step.is_done, "reasoning_step": reasoning_step}

    parse_react_output = AgentFnComponent(fn=parse_react_output_fn)

    def run_tool_fn(
        task: Task, state: Dict[str, Any], reasoning_step: ActionReasoningStep
    ):
        """Run tool and process tool output."""
        tool_runner_component = ToolRunnerComponent(
            [tool], callback_manager=task.callback_manager
        )
        tool_output = tool_runner_component.run_component(
            tool_name=reasoning_step.action,
            tool_input=reasoning_step.action_input,
        )
        observation_step = ObservationReasoningStep(observation=str(tool_output))
        state["current_reasoning"].append(observation_step)
        # TODO: get output

        return {"response_str": observation_step.get_content(), "is_done": False}

    run_tool = AgentFnComponent(fn=run_tool_fn)

    def process_response_fn(
        task: Task, state: Dict[str, Any], response_step: ResponseReasoningStep
    ):
        """Process response."""
        state["current_reasoning"].append(response_step)
        response_str = response_step.response
        # Now that we're done with this step, put into memory
        state["memory"].put(ChatMessage(content=task.input, role=MessageRole.USER))
        state["memory"].put(
            ChatMessage(content=response_str, role=MessageRole.ASSISTANT)
        )

        return {"response_str": response_str, "is_done": True}

    process_response = AgentFnComponent(fn=process_response_fn)

    def process_agent_response_fn(
        task: Task, state: Dict[str, Any], response_dict: dict
    ):
        """Process agent response."""
        return (
            AgentChatResponse(response_dict["response_str"]),
            response_dict["is_done"],
        )

    process_agent_response = AgentFnComponent(fn=process_agent_response_fn)

    pipeline = QueryPipeline(verbose=True)
    pipeline.add_modules(
        {
            "agent_input": agent_input_component,
            "react_prompt": react_prompt_component,
            "llm": Settings.llm,
            "react_output_parser": parse_react_output,
            "run_tool": run_tool,
            "process_response": process_response,
            "process_agent_response": process_agent_response,
            "retriever": retriever,
        }
    )

    # if synthesize_response:
    #     pipeline.add_modules(
    #         {
    #             "synthesizer": get_response_synthesizer(
    #                 response_mode=response_mode, streaming=True
    #             )
    #         }
    #     )

    # pipeline.add_link("synthesizer", "llm")
    # pipeline.add_link("agent_input", "retriever")
    # pipeline.add_link("retriever", "synthesizer", dest_key="nodes")
    # pipeline.add_link("agent_input", "synthesizer", dest_key="query_str")

    # link input to react prompt to parsed out response (either tool action/input or observation)
    pipeline.add_chain(["agent_input", "react_prompt", "llm", "react_output_parser"])

    # add conditional link from react output to tool call (if not done)
    pipeline.add_link(
        "react_output_parser",
        "run_tool",
        condition_fn=lambda x: not x["done"],
        input_fn=lambda x: x["reasoning_step"],
    )
    # add conditional link from react output to final response processing (if done)
    pipeline.add_link(
        "react_output_parser",
        "process_response",
        condition_fn=lambda x: x["done"],
        input_fn=lambda x: x["reasoning_step"],
    )

    # whether response processing or tool output processing, add link to final agent response
    pipeline.add_link("process_response", "process_agent_response")
    pipeline.add_link("run_tool", "process_agent_response")

    return pipeline


def main():
    parse_args_and_setup()

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


if __name__ == "__main__":
    main()
