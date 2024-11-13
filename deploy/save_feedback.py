from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# CSV 文件名
csv_file = '/home/ChatDKU_Deployment/ChatDKU/deploy/feedback/feedback.csv'

@app.route('/save-feedback', methods=['POST'])
def save_feedback():
    data = request.get_json()
    user_input = data['userInput']
    bot_answer = data['botAnswer']
    feedback_reason = data['feedbackReason']
    question_id = data['chatHistoryId']

    # 检查文件是否存在，如果不存在则写入列名
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        # 如果文件不存在，写入列名
        if not file_exists:
            writer.writerow(['input', 'chatHistoryId', 'answer', 'feedback_reason'])
        writer.writerow([user_input, question_id, bot_answer, feedback_reason])

    return jsonify({'message': 'Feedback saved successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9013)