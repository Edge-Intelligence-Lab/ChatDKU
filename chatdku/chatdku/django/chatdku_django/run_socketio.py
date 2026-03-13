#!/usr/bin/env python
"""
独立的 Socket.IO 服务器用于语音转文字功能
需要单独运行：python run_socketio.py
"""
import os
import sys
import django
from aiohttp import web

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatdku_django.settings')
django.setup()

from stt.socketio_server import sio
from stt import handlers  # 导入以注册事件处理器

async def init_app():
    """初始化 Socket.IO 应用"""
    app = web.Application()
    sio.attach(app)
    return app

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)

    host = os.getenv('STT_HOST', '0.0.0.0')
    port = int(os.getenv('STT_PORT', '8007'))

    print(f"Starting Socket.IO server on {host}:{port}")
    print("Press Ctrl+C to stop")

    web.run_app(init_app(), host=host, port=port)
