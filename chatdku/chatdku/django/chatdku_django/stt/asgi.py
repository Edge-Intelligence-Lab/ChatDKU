import socketio
from aiohttp import web
from .socketio_server import sio
from . import handlers  # 导入处理器以注册事件


async def socketio_app():
    """创建 Socket.IO ASGI 应用"""
    app = web.Application()
    sio.attach(app)
    return app
