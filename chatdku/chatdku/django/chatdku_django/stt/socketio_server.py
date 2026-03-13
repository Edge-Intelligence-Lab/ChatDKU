import socketio
import os
from django.conf import settings

# 创建 Socket.IO 服务器实例
sio = socketio.AsyncServer(
    async_mode='aiohttp',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=False
)
