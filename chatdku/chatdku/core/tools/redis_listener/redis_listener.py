import dotenv
import os
import sys
import time
import json
import logging
import redis
import threading
from datetime import datetime

from chatdku.chatdku.config import config
from chatdku.chatdku.core.tools.email.email_tool import EmailTools

dotenv.load_dotenv()

# ------------ Redis 连接配置 ------------
REDIS_HOST = config.redis_host
REDIS_PASSWORD = config.redis_password
REDIS_PORT = 6379
DB = 0
KEYEVENT_DEL = f"__keyevent@{DB}__:del"
KEYEVENT_EX = f"__keyevent@{DB}__:expired"


# ------------ Logging ------------
LOG_FILE = os.getenv("REDIS_LISTENER_LOG_FILE", "./logs/redis_listener.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logger = logging.getLogger("redis_listener")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
)

if not logger.hasHandlers():
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

deleted_keys_buffer = []
last_email_time = datetime.now()

EMAIL_INTERVAL = 300  # 秒（5分钟）

redis_down = False
redis_down_alert_sent = False
redis_down_logs = []
MAX_DOWN_LOGS = 5

REDIS_DOWN_START = None
DOWN_ALERT_AFTER = 180  # 3 分钟

MAX_BUFFER = 5000

buffer_lock = threading.Lock()


def flush_email_summary():
    """将当前缓存中的删除 key 汇总后发送邮件"""
    global deleted_keys_buffer, last_email_time

    with buffer_lock:
        if not deleted_keys_buffer:
            return
        total = len(deleted_keys_buffer)
        index = deleted_keys_buffer[0].split(":")[0]
        normalized_prefix = index.replace("_doc", "")
        deleted_keys_buffer = []
        last_email_time = datetime.now()

    subject = f"[ChatDKU Alert] Redis Deleted Keys Summary ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    message = (
        f"{total} Redis keys from {normalized_prefix} were deleted in the last 5 minutes.\n"
        "Keys are omitted from email for safety."
    )
    if normalized_prefix == config.index_name:
        try:
            send_email_alert(message, subject_override=subject)
            logger.info(f"Summary email sent for {total} deleted keys.")
        except Exception as e:
            logger.error(f"Error sending summary email: {e}")


def schedule_email_flush():
    """后台线程定期检查并发送汇总邮件"""
    while True:
        now = datetime.now()
        if (now - last_email_time).total_seconds() >= EMAIL_INTERVAL:
            flush_email_summary()
        elif len(deleted_keys_buffer) >= MAX_BUFFER:
            flush_email_summary()
        time.sleep(30)  # 每30秒检查一次


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
def send_email_alert(key_name: str = None, subject_override: str = None):
    """发送报警邮件，可单 key 或汇总"""
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", 25))
    from_email = os.getenv("EMAIL_HOST_USER")
    to_email = os.getenv("EMAIL_TO")

    if not all([host, port, from_email, to_email]):
        logger.error("Missing email configuration. Check .env file.")
        return

    try:
        to_email_list = json.loads(to_email)
        name = "ChatDKU"
        subject = subject_override or "[ChatDKU Alert] Redis Key Deleted"
        message = key_name or "Redis event triggered."
        email = EmailTools(
            host=host,
            port=port,
            receiver_email=to_email_list,
            sender_name=name,
            sender_email=from_email,
        )
        result = email.send_mail(subject, message)
        logger.info(f"Email sent ({result})")
    except Exception as e:
        logger.error(f"Error sending alert email: {e}")


# ------------ 主循环 ------------
def run_listener():
    global redis_down, redis_down_alert_sent, redis_down_logs, REDIS_DOWN_START
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
            if redis_down:
                logger.info("Redis connection restored.")
                # 重置状态
                redis_down = False
                redis_down_alert_sent = False
                redis_down_logs = []
                REDIS_DOWN_START = None

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
                    if should_log_key(key):
                        with buffer_lock:
                            deleted_keys_buffer.append(key)

        except redis.exceptions.ConnectionError as e:
            now = datetime.now()
            if REDIS_DOWN_START is None:
                REDIS_DOWN_START = now  # 第一次检测到掉线
                logger.warning("Redis connection error. Starting downtime counter...")

            down_seconds = (now - REDIS_DOWN_START).total_seconds()

            if not redis_down:
                redis_down = True
                redis_down_alert_sent = False

            if len(redis_down_logs) < MAX_DOWN_LOGS:
                redis_down_logs.append(str(e))

            logger.warning(f"Redis connection error: {e}. Reconnecting in 5s...")
            if down_seconds >= DOWN_ALERT_AFTER and not redis_down_alert_sent:
                subject = "[ChatDKU Alert] Redis DOWN (3+ minutes)"
                msg = (
                    f"Redis has been DOWN for {int(down_seconds)} seconds.\n\n"
                    "Recent error logs (up to 5):\n" + "\n".join(redis_down_logs)
                )
                try:
                    send_email_alert(msg, subject_override=subject)
                    redis_down_alert_sent = True
                    logger.warning("Redis down alert email sent after 3 minutes.")
                except Exception as mail_err:
                    logger.error(f"Error sending Redis down email: {mail_err}")

            time.sleep(5)

        except Exception as e:
            logger.error(f"Listener error: {e}. Reconnecting in 5s...")
            time.sleep(5)


if __name__ == "__main__":
    threading.Thread(target=schedule_email_flush, daemon=True).start()
    run_listener()
