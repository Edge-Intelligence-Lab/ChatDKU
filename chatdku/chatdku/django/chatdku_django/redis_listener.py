import os
import sys
import time
import json
import logging
import redis
import django

# ------------ Django 初始化 ------------
sys.path.append("chatdku/chatdku/django/chatdku_django")  # 修改为 manage.py 所在目录
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatdku_django.settings")
django.setup()

from ChatDKU.chatdku.chatdku.config import config
from chatdku_django import settings
from chat.mail import EmailUtil  # 路径改为你项目中 EmailUtil 所在模块

# ------------ Redis 连接配置 ------------
REDIS_HOST = config.redis_host
REDIS_PASSWORD = config.redis_password 
REDIS_PORT = 6379
DB = 0
KEYEVENT_DEL = f"__keyevent@{DB}__:del"
KEYEVENT_EX = f"__keyevent@{DB}__:expired"


# ------------ Logging ------------
LOG_FILE = "/datapool/redis_listener/redis_listener.log"
logger = logging.getLogger("redis_listener")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(console_handler)

# ------------ 监听配置 ------------
def ensure_notify_keyspace_events(r: redis.Redis, required_flags: str = "Egx"):
    """确保 Redis 事件通知开启"""
    try:
        cur = r.config_get("notify-keyspace-events").get("notify-keyspace-events", "")
    except Exception:
        cur = ""
    if all(flag in cur for flag in ("E", "g", "x")):
        return True
    new = "".join(sorted(set(cur + required_flags)))
    try:
        r.config_set("notify-keyspace-events", new)
        logger.info(f"notify-keyspace-events updated to: {new}")
        return True
    except Exception:
        return False

def should_log_key(key: str) -> bool:
    """过滤系统键"""
    ignore_prefixes = ("celery", "unacked", "redis", "rq:", "flower", "_kombu")
    return not key.startswith(ignore_prefixes)

# ------------ 邮件通知 ------------
def send_alert_via_django(key_name: str):
    """调用 Django EmailUtil 发送报警"""
    try:
        from_email = os.getenv("EMAIL_HOST_USER")
        to_email = os.getenv("EMAIL_TO")  # JSON 格式字符串
        subject = f"[ChatDKU Alert] Redis key deleted: {key_name}"
        content_text = f"Alert: Redis key deleted -> {key_name}"

        EmailUtil.send_mail(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            content_text=content_text,
            content_html=f"<p>{content_text}</p>",
            add_logo=False
        )
        logger.info(f"Alert email sent for key: {key_name}")
    except Exception as e:
        logger.error(f"Error sending alert via Django EmailUtil: {e}")

# ------------ 主循环 ------------
def run_listener():
    logger.info("Starting Redis Key Event Listener...")

    while True:
        try:
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                db=DB,
                decode_responses=True,
                socket_keepalive=True,
            )

            r.ping()
            logger.info(f"Connected to Redis {REDIS_HOST}:{REDIS_PORT}")

            ensure_notify_keyspace_events(r)
            pubsub = r.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(KEYEVENT_DEL, KEYEVENT_EX)
            logger.info(f"Listening for events on: {KEYEVENT_DEL}, {KEYEVENT_EX}")

            for msg in pubsub.listen():
                if msg is None or msg.get("type") != "message":
                    continue
                channel = msg.get("channel")
                key = msg.get("data")

                if not should_log_key(key):
                    continue

                if "expired" in channel:
                    logger.info(f"Key expired -> {key}")
                    continue

                if "del" in channel:
                    logger.warning(f"Key deleted -> {key}")
                    send_alert_via_django(key)

        except redis.exceptions.ConnectionError as e:
            logger.warning(f"Redis connection error: {e}. Reconnecting in 5s...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Listener error: {e}. Reconnecting in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    run_listener()