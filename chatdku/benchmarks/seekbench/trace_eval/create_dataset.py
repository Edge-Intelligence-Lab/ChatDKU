import pandas as pd
import argparse
import os
from prompts import QA_PROMPT
from chatdku.config import config
import chromadb
from openai import AsyncOpenAI
from dotenv import load_dotenv
import re
import json
import asyncio
import random
import tqdm

load_dotenv()

parser = argparse.ArgumentParser()
parser.add_argument("--output_path", type=str, required=True)
parser.add_argument("--concurrency", type=int, required=True)
parser.add_argument("--num_samples", type=int, default=20)
parser.add_argument("--model", required=True)


def append_to_jsonl(file_path, data_list):
    with open(file_path, "a") as f:
        for item in data_list:
            f.write(json.dumps(item) + "\n")


async def _query_llm(client, chunk, model, max_attempt=3, delay=0.5):
    prompt = QA_PROMPT.format(chunk=chunk)

    for attempt in range(max_attempt):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            print("\n" + "="*40)
            print("RAW LLM RESPONSE:")
            print(content)
            print("="*40 + "\n")

            try:
                data = json.loads(content)
            except:
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                else:
                    raise ValueError("Invalid JSON")

            qa_pairs = data.get("qa_pairs", [])
            return qa_pairs if isinstance(qa_pairs, list) else []

        except Exception as e:
            print(f"Error: {e} | attempt {attempt+1}")
            if attempt + 1 == max_attempt:
                return []
            await asyncio.sleep(delay)

    return []


async def main():
    args = parser.parse_args()

    chroma_db = chromadb.HttpClient(host="localhost", port=config.chroma_db_port)
    collection = chroma_db.get_collection(name="dku_html_pdf")
    collection_data = collection.get()['documents']

    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE") or None,
    )

    semaphore = asyncio.Semaphore(args.concurrency)

    indices = list(range(len(collection_data) - 22))
    random.shuffle(indices)
    indices = indices[:args.num_samples]

    async def generate_qa(idx):
        async with semaphore:
            if idx + 15 > len(collection_data):
                return []

            chunks = collection_data[idx:idx + 20]

            qa_list = await _query_llm(
                client=client,
                chunk=chunks,
                model=args.model
            )

            for item in qa_list:
                item["source_idx"] = idx

            return qa_list

    tasks = [generate_qa(i) for i in indices]

    output_file = os.path.abspath(args.output_path)
    jsonl_file = output_file.replace(".parquet", ".jsonl")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    results_count = 0
    failures = 0

    for future in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Writing QA"):
        qa_list = await future

        if qa_list:
            append_to_jsonl(jsonl_file, qa_list)
            results_count += len(qa_list)
        else:
            failures += 1

        if results_count % 50 == 0 and results_count > 0:
            print(f"Saved {results_count} QA pairs | Failures: {failures}")

    if os.path.exists(jsonl_file):
        df = pd.read_json(jsonl_file, lines=True)
        df.to_parquet(output_file)
        print(f"Final dataset saved: {output_file}")
        print(f"Total QA pairs: {len(df)} | Failures: {failures}")


if __name__ == "__main__":
    asyncio.run(main())