import os
import sys
import django

import os
import sys
import time
import json
import logging
import redis
import django
import dotenv


dotenv.load_dotenv()

from ChatDKU.chatdku.chatdku.config import config
from ChatDKU.chatdku.chatdku.core.tools.email.email_tool import EmailTools  

# # ---- Django 初始化 ----
# sys.path.append("chatdku/chatdku/django/chatdku_django")  # 改为 manage.py 所在目录
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatdku_django.settings")
# django.setup()

# from chat.mail import EmailUtil
# from chatdku_django import settings

def test_email():
    host = os.getenv("EMAIL_HOST")
    port = os.getenv("EMAIL_PORT")
    from_email = os.getenv("EMAIL_HOST_USER")
    to_email = os.getenv("EMAIL_TO")

    if not to_email:
        raise ValueError("EMAIL_TO not set in .env")
    to_email_list = json.loads(to_email)

    name = "ChatDKU"
    subject = "[ChatDKU Test] Django Email Connection"
    message = "This is a test email sent from Django."

    try:
        email = EmailTools(host=host,port=port,receiver_email=to_email_list,sender_name=name,sender_email=from_email)
        result = email.send_mail(subject, message)
        print(result)
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    test_email()