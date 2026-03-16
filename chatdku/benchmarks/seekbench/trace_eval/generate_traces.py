from chatdku.core.agent import Agent
from chatdku.core.tools.llama_index import KeywordRetrieverOuter, VectorRetrieverOuter
import dspy
from openinference.instrumentation import dangerously_using_project
from phoenix.otel import register
import ray
import argparse

parser=argparse.ArgumentParser()
parser.add_argument("--file_path",help = "File path for parquet file (questions)",required = True)


# tracer_provider = register(
#     project_name="evals"
# )


def read_questions_parquet(path: str) -> list[dict]:
    ray.init(ignore_reinit_error=True)
    ds = ray.data.read_parquet(path)
    df = ds.to_pandas()
    records = df[["question", "max_iteration"]].to_dict(orient="records")
    return records[400:420:2]



@ray.remote
def _run_agent_remote(idx: int, question: str, max_iterations: int = 2) -> None:
    from chatdku.config import config
    from chatdku.setup import setup, use_phoenix

    setup()
    use_phoenix()
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
    # with dangerously_using_project("evals"):
    agent = Agent(
        max_iterations=max_iterations,
        streaming=True,
        get_intermediate=False,
        tools=tools,
    )
    responses_gen = agent(
        current_user_message=question,
    )
    full_response = ""
    for r in responses_gen.response:
        full_response += r

    print(f"----\n{question}\nresponse: {full_response}\n status: done\n----")



def run_multiple_agent(question: list[dict]) -> None:
    ray.init(ignore_reinit_error=True)


    futures = [
        _run_agent_remote.remote(idx, q['question'], q.get('max_iteration', 2))
        for idx, q in enumerate(question)
    ]
    ray.get(futures)

    return



def main():
    args=parser.parse_args()

    qlist=args.file_path

    records=read_questions_parquet(qlist)

    run_multiple_agent(question=records)

    return



if __name__ == "__main__":
    main()
