from chatdku.core.agent import Agent
from chatdku.core.tools.llama_index import KeywordRetrieverOuter, VectorRetrieverOuter
import dspy
import ray
import argparse
import torch

from openinference.instrumentation import dangerously_using_project
from opentelemetry import trace
import os


parser = argparse.ArgumentParser()
parser.add_argument(
    "--file_path",
    help="File path for parquet file (questions)",
    type=str,
    required=True
)

num_gpu=torch.cuda.device_count() if (torch.cuda.device_count()>=1 and torch.cuda.device_count()<=4) else 0


def read_questions_parquet(path: str) -> list[dict]:
    ds = ray.data.read_parquet(path)
    df = ds.to_pandas()
    records = df[["question", "max_iteration"]].to_dict(orient="records")
    return records[400:420:2]


@ray.remote(num_gpus=num_gpu)
def _run_agent_remote(idx: int, question: str, max_iterations: int = 2) -> None:
    """Use the custom agent to generate reasoning traces"""

    from chatdku.config import config
    from chatdku.setup import setup, use_phoenix

    setup()
    use_phoenix()

    print(f"Tracing setup completed for idx {idx}")
    print(f"Using {num_gpu} gpu")


    lm = dspy.LM(
        model="openai/" + config.backup_llm,
        api_base=config.backup_llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=config.context_window,
        temperature=config.llm_temperature,
    )

    dspy.configure(lm=lm)

    user_id = "ChatDKU"
    search_mode = 0

    tools = [
        KeywordRetrieverOuter(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id=user_id,
            search_mode=search_mode,
            files=[],
        ),
        VectorRetrieverOuter(
            retriever_top_k=10,
            use_reranker=False,
            reranker_top_n=5,
            user_id=user_id,
            search_mode=search_mode,
            files=[],
        ),
    ]

    print(f"----\n{idx+1}\n{question}\n status: pending\n----")

    agent = Agent(
        max_iterations=max_iterations,
        streaming=True,
        get_intermediate=False,
        tools=tools,
    )

    full_response = ""

    with dangerously_using_project("seekbench_eval"):

        responses_gen = agent(
            current_user_message=question,
        )

        for r in responses_gen.response:
            full_response += r

    print(f"----\n{question}\nresponse: {full_response}\n status: done\n----")

    trace.get_tracer_provider().force_flush()
    trace.get_tracer_provider().shutdown()


def run_multiple_agent(question: list[dict]) -> None:
    """Run multiple agents concurrently"""

    futures = [
        _run_agent_remote.remote(idx, q["question"], q.get("max_iteration", 2))
        for idx, q in enumerate(question)
    ]

    ray.get(futures)


def main():
    args = parser.parse_args()



    ray.init(ignore_reinit_error=True)
    file_path = os.path.abspath(args.file_path)

    records = read_questions_parquet(file_path)

    run_multiple_agent(question=records)


if __name__ == "__main__":
    main()