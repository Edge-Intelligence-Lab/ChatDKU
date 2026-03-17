
from phoenix.client import Client
import dotenv
import os
import json
import pandas as pd
import json
from utils.qa_em import compute_score_f1
import argparse

parser=argparse.ArgumentParser()
parser.add_argument("--file_path",help="Parquet fille with qa",default="trace_eval/bulletin_qa.parquet")
parser.add_argument("--output_path",help="description for output parsed traces",default="trace_eval/seek_bench.jsonl")


dotenv.load_dotenv()

def setup() -> Client :
    base_port=os.environ.get('BASE_PORT',6007)
    AUTHORIZATION=os.environ.get('AUTHORIZATION')
    if not AUTHORIZATION:
        raise EnvironmentError("Authorization key not found.")


    client = Client(
        base_url=f"http://127.0.0.1:{base_port}",
        headers={"Authorization": AUTHORIZATION}
    )

    return client


def import_parquet(file_name):
    df=pd.read_parquet(file_name)
    qa=[]

    for i in df.iterrows():
        question=i[1]['question']
        answer=i[1]['answer']
        
        qa.append({
            'question':question,
            'ground_truth':answer
        })
    return qa



def reasoning_to_tags(reasoning: dict, output: str) -> str:
    blocks = []

    step = 0
    while f"thought_{step}" in reasoning:

        thought = reasoning.get(f"thought_{step}")
        if thought:
            blocks.append(f"<think>\n{thought}\n</think>")

        tool = reasoning.get(f"tool_name_{step}")
        args = reasoning.get(f"tool_args_{step}")

        if tool and tool != "finish":
            search_payload = json.dumps(args, indent=2)
            blocks.append(f"<search>\n{search_payload}\n</search>")

        obs = reasoning.get(f"observation_{step}")
        if obs and isinstance(obs, list):

            docs = []
            doc_id = 1

            for group in obs:
                for doc in group:
                    text = doc.get("text", "").strip()
                    docs.append(f"Doc {doc_id} {text}")
                    doc_id += 1

            info = "\n".join(docs)
            blocks.append(f"<information>\n{info}\n</information>")

        step += 1

    blocks.append(f"<answer>\n{output.strip()}\n</answer>")

    return "\n\n".join(blocks)



def get_traces_and_export_jsonl(traces,input_file,output_file):

    with open(output_file,'w') as f:
        qa_pairs=import_parquet(input_file)
        trace_1 = traces[traces['span_kind'] == 'AGENT'][['context.trace_id','attributes.output.value','attributes.input.value']]
        trace_2 = traces[traces['name'] == 'LLM'][['context.trace_id','attributes.output.value']]

        trace_1 = trace_1.reset_index(drop=True)
        trace_2 = trace_2.reset_index(drop=True)

        df = trace_1.merge(trace_2, on='context.trace_id', how='inner')

        for idx,qa in enumerate(qa_pairs):
            for i in range(len(df)):
                if qa['question']==json.loads(df.iloc[i].iloc[2])['current_user_message']:
                    question=json.loads(df.iloc[i].iloc[2])['current_user_message']
                    reasoning=json.loads(df.iloc[i].iloc[1])
                    answer=df.iloc[i].iloc[3]

                    parsed_trace = f"<|im_start|>assistant\n{reasoning_to_tags(reasoning,answer)}\n<|im_end|>"
                    score=compute_score_f1(qa['ground_truth'],answer)

                    result=({
                        'question':question,
                        'sequences_str':parsed_trace,
                        'ground_truth':{'target': [qa['ground_truth']]},
                        'reward':score,
                        'is_correct': score == 1.0})
                    
                    f.write(json.dumps(result)+'\n'
                    )


def main():
    try:
        print("Running....")
        args=parser.parse_args()
        client=setup()

        traces=client.spans.get_spans_dataframe(
        project_identifier="seekbench_eval"
        )
        get_traces_and_export_jsonl(traces=traces,input_file=args.file_path,output_file=args.output_path)

    finally:
        client.projects.delete(
            project_name="seekbench_eval"
        )


if __name__=='__main__':
    main()
