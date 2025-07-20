from django.conf import settings
from celery import shared_task
import logging
import dotenv
import subprocess
from chat.utils import load_weekly_data
import datetime
from django.template.loader import render_to_string
from chat.mail import EmailUtil
import os

dotenv.load_dotenv()

logger=logging.getLogger(__name__)




#Weekly 
@shared_task
def chat_load_test_weekly():
    try:
        file_conf="../locust_weekly.conf"
        runner=subprocess.run(["locust","--config",file_conf],check=True)
        logger.info("Load Test Successful")

    except subprocess.CalledProcessError as e:
        logger.error(f"ErrorCode: {str(runner.returncode)}")
        logger.error(f"ErrorOutput: {str(runner.stderr)}")

    except Exception as e:
        logger.error(f'Chat loader error: {str(e)}')




#TODO: Merge load test and email into one 
@shared_task
def email_weekly_load():
    data={
            "date":str(datetime.datetime.now().date()),
            "locust_data":load_weekly_data()
        }
    html_content=render_to_string("email/monthly_load_test.html",data)
    from_email=os.getenv("EMAIL_HOST_USER")
    to_email=os.getenv("EMAIL_TO")
    subject="Weekly ChatDKU Load Test Result"
    body_content="ChatDKU Weekly Load Test\n"

    for item in data['locust_data']:
        body_content+=f"Type: {item['type']}\nName:{item['name']}\nRequest Count: {item['request_count']}\nFailure Count: {item['failure_count']}\nAverage Response Time: {item['average_response_time']}\nFailure Percentage: {item['failure_percentage']}\n\n"


    try:
        EmailUtil.send_mail(from_email=from_email,to_email=to_email,subject=subject,content_text=body_content,content_html=html_content)

    except Exception as e:
        logger.error(f"Error sending Weekly Load Report: {str(e)}")



#For daily task
@shared_task
def chat_load_test_daily():
    try:
        file_conf="../locust_daily.conf"
        runner=subprocess.run(["locust","--config",file_conf],check=True)
        logger.info("Daily Chat Test Successful")

    except subprocess.CalledProcessError as e:
        logger.error(f"ErrorCode: {str(runner.returncode)}")
        logger.error(f"ErrorOutput: {str(runner.stderr)}")
        from_email=os.getenv("EMAIL_HOST_USER")
        to_email=os.getenv("EMAIL_TO")
        subject="Error in ChatDKU"
        body=f"Error Occured When completing Daily Load Test at {datetime.datetime.now()}"

        EmailUtil.send_mail(from_email=from_email,to_email=to_email,subject=subject,content_text=body)

    except Exception as e:
        logger.error(f'Chat Test error: {str(e)}')



#Delete Logs
@shared_task
def delete_locust_logs():
    base_dir="../locust_log"

    try:
        for item in os.listdir(base_dir):
            file_path=os.path.join(base_dir,item)
            os.remove(file_path)

    except Exception as e:
        logger.error(f"Error in deleting locust logs: {str(e)}")








