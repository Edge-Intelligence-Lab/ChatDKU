import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

from redis import Redis


# Django Default Setting for celery
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','chatdku_django.settings')

redis_password=os.getenv("REDIS_PASSWORD")
redis_host=os.getenv("REDIS_HOST")

app=Celery('chatdku_django')
app.config_from_object('django.conf:settings',namespace='CELERY')
app.conf.broker_url = f"redis://:{redis_password}@{redis_host}:6379/0"



#set up redis
redis_client=Redis(host=redis_host,port=6379,username="default",password=redis_password,db=0)


#schedule apps
app.conf.beat_schedule={
    "remove-files-every-1day":{
        "task":"core.tasks.remove_files",
        "schedule":crontab(minute=0,hour=16) #12 a.m ocal time 
    },
    "update-user-log-every-1day":{
        "task":"core.tasks.update_user_embedding",
        "schedule":crontab(minute=20,hour=16) #12:20 am local time
    },
    "chat-load-test-every-sunday":{
        "task":"chat.tasks.chat_load_test_weekly",
        "schedule":crontab(minute=20, hour=20,day_of_week=0) #Every Sunday 
    },
    "delete-load-test-logs-every-sunday":{
        "task":"chat.tasks.delete_locust_logs",
        "schedule":crontab(minute=20, hour=19,day_of_week=0) #Every Sunday 
    },
    "email-load-test-every-sunday":{
        "task":"chat.tasks.email_weekly_load",
        "schedule":crontab(minute=20, hour=21,day_of_week=0) #Every Sunday 
    },
    "chat-test-every-2hr":{
        "task":"chat.tasks.chat_load_test_daily",
        "schedule":crontab(minute=00, hour='*/2') # 2hr, everyday
    },
    "session-clean-admin-1day":{
        "task":"chat.tasks.clean_admin_session",
        "schedule":crontab(minute=00,hour='*/12') # Every 22hr
    },
    "session-clean-empty":{
        "task":"chat.tasks.clean_empty_sessions",
        "schedule":crontab(minute=00,hour='*/1') #Every 1 hour everyday
    },
    # "oss-test-30min":{
    #     "task":"chat.tasks.oss_test",
    #     "schedule":crontab(minute="*/30") #run every 30 mins
    # }

    "lm-check":{
        "task":"core.tasks.ping_llm",
        "schedule":crontab(minute="*/10")
    },
    "load_redis_daily":{
        "task":"core.tasks.load_redis_task",
        "schedule":crontab(minute=00,hour=00) #run at 8:00 am China Time
    }
}

app.autodiscover_tasks()

