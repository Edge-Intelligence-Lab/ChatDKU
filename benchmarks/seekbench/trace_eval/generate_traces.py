from chatdku.core.agent import Agent
from chatdku.core.tools.llama_index import KeywordRetrieverOuter, VectorRetrieverOuter
from chatdku.setup import setup, use_phoenix
import dspy
from chatdku.config import config
from openinference.instrumentation import dangerously_using_project
import time
import concurrent.futures


from phoenix.otel import register

tracer_provider = register(
    project_name="evals"
)


questions = [
    {"question": "What is DKU?", "max_iteration": 2},
    {"question": "Tell me about the campus facilities at DKU.", "max_iteration": 4},
    {"question": "What programs does DKU offer?", "max_iteration": 2},
    {"question": "How to apply to DKU?", "max_iteration": 2},
    {"question": "What is the student life like at DKU?", "max_iteration": 4},
]





def _run_agent(idx: int, question: str, tools: list, max_iterations: int = 2):
    print(f"----\n{idx+1}\n{question}\n status: pending\n----")

    with dangerously_using_project("evals"):
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
            full_response+=r


    print(f"----\n{question}\nresponse: {full_response}\n status: done\n----")



def run_multiple_agent(question:dict):
    user_id='ChatDKU'
    search_mode=0


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

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_run_agent, idx, q['question'], tools, q['max_iteration']) for idx, q in enumerate(question)]
        for future in concurrent.futures.as_completed(futures):
            future.result()
    
    return 



def main():
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

    run_multiple_agent(question=questions)

    return



if __name__ == "__main__":
    main()
