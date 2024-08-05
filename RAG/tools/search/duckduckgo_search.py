import os
import json
from openai import OpenAI
from duckduckgo_search import DDGS

API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL")
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

FUNCTIONS = [
    {
        "name": "search_duckduckgo",
        "description": "Use the DuckDuckGo search engine to look up information. You can search for the latest news, articles, blogs and more.",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "搜索的关键词列表。例如：['DKU','Duke Kunshan University']。"
                }
            },
            "required": ["keywords"]
        }
    }
]


def search_duckduckgo(keywords):
    search_term = " ".join(keywords)
    with DDGS() as ddgs:
        return list(ddgs.text(keywords=search_term, region="cn-zh", safesearch="on", max_results=5))


def print_search_results(results):
    for result in results:
        print(
            f"标题: {result['title']}\n链接: {result['href']}\n摘要: {result['body']}\n---")


def get_openai_response(messages, model="gpt-3.5-turbo", functions=None, function_call=None):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            functions=functions,
            function_call=function_call
        )
        return response.choices[0].message
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        return None


def process_function_call(response_message):
    function_name = response_message.function_call.name
    function_args = json.loads(response_message.function_call.arguments)

    print(f"\nModel Selection Calling Functions: {function_name}")

    if function_name == "search_duckduckgo":
        keywords = function_args.get('keywords', [])

        if not keywords:
            print("Error: Model does not provide search keywords")
            return None

        print(f"Keywords: {', '.join(keywords)}")

        function_response = search_duckduckgo(keywords)
        print("\nDuckDuckGo Response:")
        print_search_results(function_response)

        return function_response
    else:
        print(f"Unknown Function Name: {function_name}")
        return None


def main(question):
    print(f"Query：{question}")

    messages = [{"role": "user", "content": question}]
    response_message = get_openai_response(
        messages, functions=FUNCTIONS, function_call="auto")

    if not response_message:
        return

    if response_message.function_call:
        if not response_message.content:
            response_message.content = ""
        function_response = process_function_call(response_message)
        if function_response:
            messages.extend([
                response_message.model_dump(),
                {
                    "role": "function",
                    "name": response_message.function_call.name,
                    "content": json.dumps(function_response, ensure_ascii=False)
                }
            ])

            final_response = get_openai_response(messages, model="gpt-4o")
            if final_response:
                print("\nFinal answer:")
                print(final_response.content)
    else:
        print("\nDirect Answer from Model:")
        print(response_message.content)


if __name__ == "__main__":
    main("What is Duke Kunshan University?")