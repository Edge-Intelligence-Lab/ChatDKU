import os
import sys
import django

# ---- Django 初始化 ----
sys.path.append("chatdku/chatdku/django/chatdku_django")  # 改为 manage.py 所在目录
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatdku_django.settings")
django.setup()

from chat.mail import EmailUtil
# from chatdku_django import settings

def test_email():
    from_email = os.getenv("EMAIL_HOST_USER")
    to_email = os.getenv("EMAIL_TO")
    subject = "[ChatDKU Test] Django Email Connection"
    message = "This is a test email sent from Django."
    
    try:
        EmailUtil.send_mail(from_email,to_email,subject, message)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    test_email()