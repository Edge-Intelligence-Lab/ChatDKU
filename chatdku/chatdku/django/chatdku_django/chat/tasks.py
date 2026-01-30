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
from django.core.cache import cache
from chat.models import UserSession
from django.contrib.auth import get_user_model

from django.db.models import Q
from core.models import hash_netid
from chat.utils import ping_lm
from core.utils import get_admin_email

dotenv.load_dotenv()

logger=logging.getLogger(__name__)

User=get_user_model()


TO_EMAIL=get_admin_email()




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
    subject="Weekly ChatDKU Test Result"
    body_content="ChatDKU Weekly Load Test\n"





    for item in data['locust_data']:
        body_content+=f"Type: {item['type']}\nName:{item['name']}\nRequest Count: {item['request_count']}\nFailure Count: {item['failure_count']}\nAverage Response Time: {item['average_response_time']}\nFailure Percentage: {item['failure_percentage']}\n\n"

    try:
        EmailUtil.send_mail(from_email=from_email,to_email=TO_EMAIL,subject=subject,content_text=body_content,content_html=html_content,add_logo=True)

    except Exception as e:
        logger.error(f"Error sending Weekly Load Report: {str(e)}")

FAILURE_THRESHOLD=6
COUNTER_KEY = "chat_load_test_daily:failures"


#For daily task
@shared_task
def chat_load_test_daily():
    try:
        file_conf=os.path.join(settings.BASE_DIR,"locust_daily.conf")
        locust_path=os.getenv("LOCUST_PATH")
        runner=subprocess.Popen([locust_path,"--config",file_conf],stderr=subprocess.PIPE,stdout=subprocess.PIPE, text=True)
        logger.info("Daily Chat Test Successful")
        
        for line in runner.stderr:
            if "ResponseLengthError" in line:
                failures=cache.incr(COUNTER_KEY,1) if cache.get(COUNTER_KEY) else 1
                if failures==1:
                    cache.set(COUNTER_KEY,1,timeout=60*60) #1hr
                if failures>=FAILURE_THRESHOLD: #Prevent unnecessary emails
                    from_email=os.getenv("EMAIL_HOST_USER")
                    subject="Error in ChatDKU Response"
                    body=f"<h1>Test Error: Error Identified</h1><p>Error Occured When completing ChatDKU Test at {datetime.datetime.now()}</p><h3>The response length does not meet the requirement set by the admin.</h3> <code>{line}</code>"
                    body_text=f"Test Error: Error Identified\nError Occured When completing ChatDKU Test at {datetime.datetime.now()}.\n The response length does not meet the requirement set by the admin. Output:\n {line}"

                    EmailUtil.send_mail(from_email=from_email,to_email=TO_EMAIL,subject=subject,content_text=body_text,content_html=body)
                    logger.info("Email sent on: ",datetime.datetime.now())
                    cache.delete(COUNTER_KEY)
                    return


    except subprocess.CalledProcessError as e:
        failures=cache.incr(COUNTER_KEY,1) if cache.get(COUNTER_KEY) else 1

        if failures==1:
            cache.set(COUNTER_KEY,1,timeout=60*60) #1hr


        logger.error(f"ErrorCode: {str(e.returncode)}")
        logger.error(f"ErrorOutput: {str(e.stderr)}")
        if failures>=FAILURE_THRESHOLD: #Prevent unnecessary emails
            from_email=os.getenv("EMAIL_HOST_USER")
            subject="Error in ChatDKU"
            body=f"<h1>Test Error: Error Identified</h1><p>Error Occured When completing ChatDKU Test at {datetime.datetime.now()}</p>\n<h4>Error Code: </h4><p>{e.returncode}</p>\n <h4>Error Output:</h4><p>{e.stderr}</p>"
            body_text=f"Test Error: Error Identified\nError Occured When completing ChatDKU Test at {datetime.datetime.now()}\n Error Code: {e.returncode}\nError Output: {e.stderr}"

            EmailUtil.send_mail(from_email=from_email,to_email=TO_EMAIL,subject=subject,content_text=body_text,content_html=body)

            logger.info("Email sent on: ",datetime.datetime.now())
            cache.delete(COUNTER_KEY)
            return 

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

@shared_task
def clean_admin_session():
    try:
        admin_session=os.getenv("UID",'chatdku_admin')
        hashed_id=hash_netid(admin_session) if "admin" not in admin_session else admin_session 
        query=UserSession.objects.filter(user__username=hashed_id).delete()

    except Exception as e:
        logger.error(f"Error occured while cleaning admin session: {e}")

@shared_task
def clean_empty_sessions():
    try:
        query=UserSession.objects.all().filter(Q(title='')|Q(title__isnull=True)).delete()
    except Exception as e:
        logger.error(f"Error cleaning empty sessions: {e}")


# @shared_task(bind=True, max_retries=5)
def lm_test(self):
    try:
        chat_response = ping_lm("What can you do?")
        return "Pass"
    except Exception as e:
        if self.request.retries >= self.max_retries:
            if not cache.get("oss_test:fail"):
                cache.set("oss_test:fail", 1, timeout=60*60*5)

                from_email = os.getenv("EMAIL_HOST_USER")
                subject = "Error in Primary LLM"
                body_html = (
                    f"<h2>Issue Identified: LLM</h2>"
                    f"<p>GPT OSS has stopped responding since {datetime.datetime.now()}."
                    f" Please look into it!</p>"
                )
                body_text = (
                    f"Issue Identified: LLM\n"
                    f"Primary LLM has stopped responding since {datetime.datetime.now()}."
                    f" Please look into it!"
                )

                EmailUtil.send_mail(
                    from_email=from_email,
                    to_email=TO_EMAIL,
                    subject=subject,
                    content_text=body_text,
                    content_html=body_html,
                )

                logger.info(f"Email sent on: {datetime.datetime.now()}")
            raise e
        raise self.retry(exc=e, countdown=5)


