from django.conf import settings
from celery import shared_task
import logging
import dotenv
import subprocess
from chat.utils import load_weekly_data,feedback_summary
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
        file_conf=os.path.join(settings.BASE_DIR,"locust_weekly.conf")
        locust_path=os.getenv("LOCUST_PATH")

        runner=subprocess.run([locust_path,"--config",file_conf],check=True,capture_output=True,text=True)
        logger.info("Load Test Successful")

    except subprocess.CalledProcessError as e:
        logger.error(f"ErrorCode: {str(e.returncode)}")
        logger.error(f"ErrorOutput: {str(e.stderr)}")

    except Exception as e:
        logger.error(f'Chat loader error: {str(e)}')




#TODO: Merge load test and email into one 
@shared_task
def email_weekly_load():
    data={
            "date":str(datetime.datetime.now().date()),
            "locust_data":load_weekly_data(),
            "feedback_report":feedback_summary()
        }
    html_content=render_to_string("email/weekly_report.html",data)
    from_email=os.getenv("EMAIL_HOST_USER")
    to_email=os.getenv("EMAIL_TO")
    subject="Weekly ChatDKU Test Result"
    body_content="ChatDKU Weekly Load Test\n"

    for item in data['locust_data']:
        body_content+=f"Type: {item['type']}\nName:{item['name']}\nRequest Count: {item['request_count']}\nFailure Count: {item['failure_count']}\nAverage Response Time: {item['average_response_time']}\nFailure Percentage: {item['failure_percentage']}\n\n"

    try:
        EmailUtil.send_mail(from_email=from_email,to_email=to_email,subject=subject,content_text=body_content,content_html=html_content)

    except Exception as e:
        logger.error(f"Error sending Weekly Load Report: {str(e)}")

FAILURE_THRESHOLD=6

#For daily task
@shared_task
def chat_load_test_daily():
    try:
        file_conf=os.path.join(settings.BASE_DIR,"locust_daily.conf")
        locust_path=os.getenv("LOCUST_PATH")
        runner=subprocess.run([locust_path,"--config",file_conf],check=True, capture_output=True, text=True)
        logger.info("Daily Chat Test Successful")
        cnt=0
        

    except subprocess.CalledProcessError as e:
        cnt+=1

        logger.error(f"ErrorCode: {str(e.returncode)}")
        logger.error(f"ErrorOutput: {str(e.stderr)}")
        if cnt>=FAILURE_THRESHOLD: #Prevent unnecessary emails
            from_email=os.getenv("EMAIL_HOST_USER")
            to_email=os.getenv("EMAIL_TO")
            subject="Error in ChatDKU"
            body=f"<h1>Daily Load Test: Error Identified</h1><p>Error Occured When completing Daily Load Test at {datetime.datetime.now()}</p>\n<h4>Error Code: </h4><p>{e.returncode}</p>\n <h4>Error Output:</h4><p>{e.stderr}</p>"
            body_text=f"Daily Load Test: Error Identified\nError Occured When completing Daily Load Test at {datetime.datetime.now()}\n Error Code: {e.returncode}\nError Output: {e.stderr}"

            EmailUtil.send_mail(from_email=from_email,to_email=to_email,subject=subject,content_text=body_text,content_html=body)
            cnt=0

    except Exception as e:
        logger.error(f'Chat Test error: {str(e)}')



#Delete Logs
@shared_task
def delete_locust_logs():
    base_dir=os.path.join(settings.BASE_DIR,"locust_log")

    try:
        for item in os.listdir(base_dir):
            file_path=os.path.join(base_dir,item)
            os.remove(file_path)

    except Exception as e:
        logger.error(f"Error in deleting locust logs: {str(e)}")
