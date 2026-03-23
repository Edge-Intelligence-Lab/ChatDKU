from phoenix.client import Client
import dotenv
import os
import json
import pandas as pd
from utils.qa_em import compute_score_f1
import argparse
import uuid

parser = argparse.ArgumentParser()
parser.add_argument("--file_path", required=True, help="Parquet file with QA")
parser.add_argument("--output_path", required=True, help="Output JSONL path")
parser.add_argument("--model", default="Unknown", help="Model name")
parser.add_argument("--dataset", default="Unknown", help="Dataset name")


dotenv.load_dotenv()

def setup() -> Client:
    base_port = os.environ.get('BASE_PORT', 6007)
    AUTHORIZATION = os.environ.get('AUTHORIZATION')

    if not AUTHORIZATION:
        raise EnvironmentError("Authorization key not found.")

    return Client(
        base_url=f"http://127.0.0.1:{base_port}",
        headers={"Authorization": AUTHORIZATION}
    )


def safe_json_load(x):
    try:
        return json.loads(x)
    except Exception:
        return {}

def normalize(text: str) -> str:
    return text.strip().lower()


def import_parquet(file_name):
    df = pd.read_parquet(file_name)
    qa = []

    for _, row in df.iterrows():
        qa.append({
            'question': row['question'],
            'ground_truth': row['ground_truth']  # assume already list or string
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
            payload = json.dumps(args, indent=2)
            blocks.append(f"<search>\n{payload}\n</search>")

        obs = reasoning.get(f"observation_{step}")
        if obs and isinstance(obs, list):
            docs = []
            doc_id = 1

            for group in obs:
                for doc in group:
                    text = doc.get("text", "").strip()
                    docs.append(f"Doc {doc_id}: {text}")
                    doc_id += 1

            blocks.append(f"<information>\n" + "\n".join(docs) + "\n</information>")

        step += 1

    blocks.append(f"<answer>\n{output.strip()}\n</answer>")

    return "\n\n".join(blocks)


def build_trace_map(df):
    trace_map = {}

    for _, row in df.iterrows():
        print(row.keys())
        input_data = safe_json_load(row['agent_input'])
        question = input_data.get('current_user_message')

        if question:
            trace_map[normalize(question)] = row

    return trace_map

def get_traces_and_export_jsonl(traces, input_file, output_file, model, dataset):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    qa_pairs = import_parquet(input_file)

    trace_1 = traces[traces['span_kind'] == 'AGENT'][
        ['context.trace_id', 'attributes.output.value', 'attributes.input.value']
    ]

    trace_2 = traces[traces['name'] == 'LLM'][
        ['context.trace_id', 'attributes.output.value']
    ]

    trace_1 = trace_1.reset_index(drop=True)
    trace_2 = trace_2.reset_index(drop=True)
    print(trace_1.keys())
    print(trace_2.keys())

    df = trace_1.merge(trace_2, on='context.trace_id', how='inner')

    df.columns = [
        'trace_id',
        'agent_output',
        'agent_input',
        'llm_output'
    ]

    trace_map = build_trace_map(df)

    with open(output_file, 'w') as f:
        for qa in qa_pairs:
            key = normalize(qa['question'])
            row = trace_map.get(key)

            if row is None:
                continue

            reasoning = safe_json_load(row['agent_output'])
            if not isinstance(reasoning, dict):
                reasoning = {}

            answer = row['llm_output']

            parsed_trace = (
                "<|im_start|>assistant\n"
                f"{reasoning_to_tags(reasoning, answer)}\n"
                "<|im_end|>"
            )

            score = compute_score_f1(qa['ground_truth'], answer)

            result = {
                'id': str(uuid.uuid4()),
                'question': qa['question'],
                'sequences_str': parsed_trace,
                'ground_truth': {'target': qa['ground_truth']},
                'reward': score,
                'model': model,
                'dataset': dataset,
                'is_correct': score >= 0.6
            }

            f.write(json.dumps(result) + '\n')

def main():
    print("Running...")

    args = parser.parse_args()
    client = setup()

    print("Fetching traces...")

    traces = client.spans.get_spans_dataframe(
        project_identifier="seekbench_eval",
        timeout=500
    )

    output_file = os.path.abspath(args.output_path)
    input_path = os.path.abspath(args.file_path)

    get_traces_and_export_jsonl(
        traces=traces,
        input_file=input_path,
        output_file=output_file,
        model=args.model,
        dataset=args.dataset
    )

    print("Done.")


if __name__ == '__main__':
    main()