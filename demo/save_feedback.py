from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import os

app = Flask(__name__)
CORS(app)

# CSV 文件名
csv_file = 'feedback.csv'

@app.route('/save-feedback', methods=['POST'])
def save_feedback():
    data = request.get_json()
    user_input = data['userInput']
    bot_answer = data['botAnswer']

    # 检查文件是否存在，如果不存在则写入列名
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        # 如果文件不存在，写入列名
        if not file_exists:
            writer.writerow(['input', 'answer'])
        writer.writerow([user_input, bot_answer])

    return jsonify({'message': 'Feedback saved successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
