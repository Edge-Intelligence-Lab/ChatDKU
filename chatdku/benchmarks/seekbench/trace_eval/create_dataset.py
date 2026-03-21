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

parser=argparse.ArgumentParser()
parser.add_argument("--output_path",help="Path for output",type=str,required=True)
parser.add_argument("--concurrency",help="Path for output",type=int,required=True)
parser.add_argument("--num_samples",help="Number of tasks to run (questions to produce)",type=int, default=20)
parser.add_argument("--model",help="Model used in qa generation",required = True)

async def _query_llm(client,chunk,model,max_attempt=5,delay=3):
    """Query the LLM to generate QA pair. Calls the OpenAI API with retry logic and the most robust JSON parsing"""
    prompt=QA_PROMPT.format(chunk=chunk)
    for attempt in range(max_attempt):
        try:
            response= await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content

            try:
                return json.loads(content)
            except:
                match = re.search(r'\{.*?\}', content, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            if attempt + 1 == max_attempt:
                return None
            await asyncio.sleep(delay)
            
        except Exception as e:
            print(f"Error occured: {e}\nattempt: {attempt+1}")
            if attempt + 1 == max_attempt:
                return None
            await asyncio.sleep(delay)
    return None

async def main():
    args = parser.parse_args()

    chroma_db = chromadb.HttpClient(host="localhost", port=config.chroma_db_port)
    collection = chroma_db.get_collection(name="dku_html_pdf")

    collection_data = collection.get()['documents'] 

    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE") or None,
    )

    model = args.model
    semaphore = asyncio.Semaphore(args.concurrency)

    indices = list(range(len(collection_data) - 6))
    random.shuffle(indices)
    indices = indices[:args.num_samples]

    async def generate_qa(idx):
        async with semaphore:
            chunks = collection_data[idx:idx + 5]

            response = await _query_llm(
                client=client,
                chunk=chunks,
                model=model
            )

            return response

    tasks = [generate_qa(i) for i in range(indices)]

    output_file=os.path.abspath(args.output_path)

    os.makedirs(os.path.dirname(output_file),exist_ok=True)

    results=[]
    for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Writing QA"):
        result = await future
        if result:
            results.append(result)

    df=pd.DataFrame(result)
    df.to_parquet(output_file)
