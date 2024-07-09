from flask import Flask, request, jsonify
from openai import OpenAI
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

client = OpenAI(
    api_key = "sk-jVnbKUgMMvfNpaA18283E9A9942345B89a81Cf22257a4c23",
    base_url="https://35.aigcbest.top/v1",
)

def simple_prompt_template(text):
    prompt_text = [
            {"role":"user","content":f"{text}"},
                    ]
    return prompt_text


@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    print(data)
    user_message = data.get('messages')

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  
            messages=user_message,
            max_tokens=3000,
            n=1,
            stop=None,
            temperature=0.5,
        )
        
        
        message =  response.choices[0].message.content
            # 手动编码为 JSON 字符串，并设置正确的 Content-Type
        json_data = json.dumps({'message': message}, ensure_ascii=False)
        return app.response_class(
            response=json_data,
            status=200,
            mimetype='application/json; charset=utf-8'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


