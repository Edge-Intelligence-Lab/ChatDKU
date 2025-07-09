from contextlib import contextmanager
import time
from chatdku_django.celery import redis_client
from django.core.files.storage import default_storage


@contextmanager
def redis_lock(lockkey, expire= 600):
    lock=redis_client.lock(name=lockkey,timeout=expire)
    acquired=lock.acquire(blocking=False)
    try:
        if acquired:
            yield

        else:
            raise RuntimeError("Could not acquire Lock")
    finally:
        if acquired:
            lock.release()