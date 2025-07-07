import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv


# Django Default Setting for celery
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','chatdku_django.settings')

app=Celery('chatdku_django')

app.config_from_object('django.conf:settings',namespace='CELERY')

#schedule apps
app.conf.beat_schedule={
    "remove-files-every-1day":{
        "task":"core.tasks.remove_files",
        "schedule":crontab(minute=0,hour=0)
    },
    "update-user-log-every-1day":{
        "task":"core.tasks.update_user_embedding",
        "schedule":crontab(minute=0,hour=0)
    }
}

app.autodiscover_tasks()

