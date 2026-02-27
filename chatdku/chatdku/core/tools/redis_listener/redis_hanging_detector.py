import dotenv
import os
import sys
import time
import json
import logging
import redis
from datetime import datetime
from statistics import mean
from typing import List

from chatdku.chatdku.config import config
from chatdku.chatdku.core.tools.email.email_tool import EmailTools

dotenv.load_dotenv()

# ------------ Redis 连接配置 ------------
REDIS_HOST = config.redis_host
REDIS_PASSWORD = config.redis_password
REDIS_PORT = 6379
DB = 0

# ------------ 监控配置 ------------
PING_INTERVAL = 10  # 检查间隔(秒)
SLOW_THRESHOLD = 5  # 慢响应阈值(秒)
MAX_SLOW_COUNT = 10  # 连续慢响应次数触发报警
PING_TIMEOUT = 7  # ping 超时时间(秒)
ALERT_COOLDOWN = 300  # 报警冷却时间(秒)，避免频繁发送

# ------------ Logging ------------
LOG_FILE = os.getenv("REDIS_HANGING_LOG_FILE", "./logs/redis_hanging_monitor.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logger = logging.getLogger("redis_hanging_monitor")
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


# ------------ 状态追踪 ------------
class MonitorState:
    def __init__(self):
        self.slow_count = 0
        self.latencies = []
        self.last_hanging_alert_time = None  # hanging 报警时间
        self.is_hanging = False

    def reset_slow_count(self):
        self.slow_count = 0

    def can_send_hanging_alert(self):
        """检查是否可以发送 hanging 报警"""
        if self.last_hanging_alert_time is None:
            return True
        return (time.time() - self.last_hanging_alert_time) > ALERT_COOLDOWN

    def record_hanging_alert(self):
        """记录 hanging 报警时间"""
        self.last_hanging_alert_time = time.time()


state = MonitorState()


# ------------ 邮件通知 ------------
def send_email_alert(subject: str, message: str):
    """发送报警邮件"""
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", 25))
    from_email = os.getenv("EMAIL_HOST_USER")
    to_email = os.getenv("EMAIL_TO")

    if not all([host, port, from_email, to_email]):
        logger.error("Missing email configuration. Check .env file.")
        return False

    try:
        to_email_list = json.loads(to_email)
        name = "ChatDKU"
        email = EmailTools(
            host=host,
            port=port,
            receiver_email=to_email_list,
            sender_name=name,
            sender_email=from_email,
        )
        result = email.send_mail(subject, message)
        logger.info(f"Alert email sent: {result}")
        return True
    except Exception as e:
        logger.error(f"Error sending alert email: {e}")
        return False


def report_redis_hanging(recent_latencies: List[float]):
    """报告 Redis hanging 状态"""
    if not state.can_send_hanging_alert():
        elapsed = time.time() - state.last_hanging_alert_time
        logger.warning(
            f"Hanging alert cooldown active ({int(elapsed)}s / {ALERT_COOLDOWN}s), skipping alert"
        )
        return

    avg_latency = mean(recent_latencies)
    max_latency = max(recent_latencies)

    subject = "[ChatDKU Alert] Redis HANGING - Slow Response Detected"
    message = f"""Redis instance is experiencing HANGING status (slow but still responding).

Connection Details:
- Redis Host: {REDIS_HOST}:{REDIS_PORT}
- Database: {DB}

Performance Metrics:
- Recent {len(recent_latencies)} pings average latency: {avg_latency:.3f}s
- Maximum latency: {max_latency:.3f}s
- Slow threshold: {SLOW_THRESHOLD}s
- Consecutive slow responses: {state.slow_count}

Recent latencies: {[f'{lat:.3f}s' for lat in recent_latencies]}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Action Required:
Please investigate Redis performance immediately.
"""

    if send_email_alert(subject, message):
        state.record_hanging_alert()
        state.is_hanging = True
        logger.info(f"Hanging alert sent. Next alert available in {ALERT_COOLDOWN}s")


def check_redis_health(r: redis.Redis):
    """执行 Redis 健康检查"""
    start = time.time()

    try:
        # 使用 ping 检测响应时间
        r.ping()
        latency = time.time() - start

        # 记录延迟
        state.latencies.append(latency)
        if len(state.latencies) > 100:  # 保留最近100条记录
            state.latencies = state.latencies[-100:]

        # 检查是否从 hanging 状态恢复
        if state.is_hanging:
            logger.info("Redis has recovered from hanging state")
            state.is_hanging = False

        # 检测慢响应
        if latency > SLOW_THRESHOLD:
            state.slow_count += 1
            logger.warning(
                f"Slow ping detected: {latency:.3f}s (count: {state.slow_count}/{MAX_SLOW_COUNT})"
            )

            if state.slow_count >= MAX_SLOW_COUNT:
                if not state.is_hanging:
                    logger.error(
                        f"Redis is hanging! {state.slow_count} consecutive slow responses"
                    )
                    report_redis_hanging(state.latencies[-MAX_SLOW_COUNT:])
                else:
                    # 已经在 hanging 状态，检查是否可以再次报警
                    if state.can_send_hanging_alert():
                        logger.error(
                            f"Redis still hanging! {state.slow_count} consecutive slow responses"
                        )
                        report_redis_hanging(state.latencies[-MAX_SLOW_COUNT:])
        else:
            # 正常响应，重置计数
            if state.slow_count > 0:
                logger.info(
                    f"Normal response: {latency:.3f}s, resetting slow count from {state.slow_count}"
                )
                state.reset_slow_count()

        logger.debug(f"Redis ping OK: {latency:.3f}s")

    except redis.exceptions.TimeoutError as e:
        # 超时 = hanging 状态
        logger.error(f"Redis ping timeout (hanging): {e}")
        state.slow_count += 1

        if state.slow_count >= MAX_SLOW_COUNT:
            if not state.is_hanging:
                logger.error(f"Redis is hanging! {state.slow_count} timeout responses")
                report_redis_hanging(
                    [PING_TIMEOUT] * min(state.slow_count, MAX_SLOW_COUNT)
                )
            else:
                # 已经在 hanging 状态，检查是否可以再次报警
                if state.can_send_hanging_alert():
                    logger.error(
                        f"Redis still hanging! {state.slow_count} timeout responses"
                    )
                    report_redis_hanging([PING_TIMEOUT] * MAX_SLOW_COUNT)

    except redis.exceptions.ConnectionError as e:
        # 连接错误，记录但不报警（只监控 hanging）
        logger.error(f"Redis connection error: {e}")
        state.reset_slow_count()

    except Exception as e:
        # 其他错误
        logger.error(f"Unexpected error during health check: {e}")
        state.reset_slow_count()


# ------------ 主循环 ------------
def run_monitor():
    """主监控循环"""
    logger.info("Starting Redis Hanging Monitor...")
    logger.info(f"Monitoring Redis at {REDIS_HOST}:{REDIS_PORT}")
    logger.info(f"Check interval: {PING_INTERVAL}s, Slow threshold: {SLOW_THRESHOLD}s")

    while True:
        try:
            # 使用与 listener 相同的连接方式
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                db=DB,
                decode_responses=True,
                socket_keepalive=True,
                socket_timeout=PING_TIMEOUT,
                socket_connect_timeout=PING_TIMEOUT,
            )

            # 首次连接测试
            r.ping()
            logger.info(f"Connected to Redis {REDIS_HOST}:{REDIS_PORT}")

            # 持续监控
            while True:
                check_redis_health(r)
                time.sleep(PING_INTERVAL)

        except redis.exceptions.ConnectionError as e:
            logger.warning(f"Redis connection error: {e}. Reconnecting in 5s...")
            state.reset_slow_count()
            time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
            break

        except Exception as e:
            logger.error(
                f"Unexpected error in monitor loop: {e}. Reconnecting in 5s..."
            )
            state.reset_slow_count()
            time.sleep(5)


if __name__ == "__main__":
    run_monitor()
