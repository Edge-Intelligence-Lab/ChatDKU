from chatdku_django.celery import redis_client
import json
import uuid
import logging
from core.tasks import update_user_chroma

logger=logging.getLogger(__name__)
#enqueue user task

def enqueue_user_task(netid, *args, **kwargs):
    user_queue = f"queue_key:{netid}"
    lock_key = f"user_lock:{netid}"
    task_id = str(uuid.uuid4())

    redis_client.rpush(user_queue, json.dumps({
        'id': task_id,
        'lock_key': lock_key
    }))

    redis_client.hset(f"task:{task_id}", mapping={
        "args": json.dumps(args),
        "kwargs": json.dumps(kwargs),
        "status": "pending"
    })

    redis_client.expire(f"task:{task_id}", 1200)
    logger.info(f"Queue set for user: {str(netid)}")


    if redis_client.get(f"processing:{netid}") is None:
        redis_client.set(f"processing:{netid}",1,ex=600)
        try:
            update_user_chroma.delay(netid)
        except Exception as e:
            logger.error("Error occoured")

    
