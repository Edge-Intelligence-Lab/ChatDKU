from contextlib import contextmanager
from chatdku_django.celery import redis_client
import logging

logger=logging.getLogger(__name__)

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