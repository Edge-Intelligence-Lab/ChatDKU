import openai

api_key = 'i dont know'

openai.api_key = api_key

def call_gpt(prompt, num_responses):
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=150,  
            n=num_responses, 
            stop=None, 
            temperature=0.7  
        )
        return [choice.text.strip() for choice in response.choices]
    except Exception as e:
        return [str(e)]

if __name__ == "__main__":
    # 定义prompt_list (prompt, num_responses)
    prompts = [

    ]
    
    all_responses = []

    for prompt, num_responses in prompts:
        results = call_gpt(prompt, num_responses)
        response_text = ""
        for idx, result in enumerate(results, 1):
            response_text += f"{result}\n"
        response_text += "\n"
        all_responses.append(response_text)

    with open("output.py", "w", encoding="utf-8") as file:
        file.write(all_responses)
