#!/usr/bin/env python3
# FIXME: Purge API key from the history of this file

### TODO: Create multiple app objects in advance, lock the app object for each user, and reset the app object when the user is not using it.
###TODO: Add limiter to prevent Ddos attack. Can use flask-limiter, with ePPn from Shibboleth to limit unique identity. If not possible, restricy general question over a specific IP to a specific number.


import eventlet

eventlet.monkey_patch()

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
import dspy
import logging
from logging.handlers import RotatingFileHandler

from werkzeug.middleware.proxy_fix import ProxyFix
from chatdku.setup import setup, use_phoenix
from chatdku.core.agent import Agent, CustomClient
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_admin import Admin
from config import Config
import os


app = Flask(__name__, template_folder="templates")
app.config.from_object(Config)
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_proto=1, x_host=1
)  # Let flask know it is behind a reverse proxy.

def _split_origins(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


cors_origins = _split_origins(
    os.getenv("CORS_ALLOWED_ORIGINS"), ["http://localhost:3005"]
)

CORS(app, origins=cors_origins)
socketio = SocketIO(
    app,
    cors_allowed_origins=cors_origins,
    async_mode="eventlet",
)  # Socket IO to receive audio


db = SQLAlchemy(app=app)
migrate = Migrate(app=app,db=db)
from app.admin import Base
admin_config = Admin(name="Dashboard", template_mode="bootstrap4", app=app,index_view=Base())

setup()
use_phoenix()
llama_client = CustomClient()
dspy.settings.configure(lm=llama_client)
agent = Agent(max_iterations=5, streaming=True, get_intermediate=False)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')

    file_handler=RotatingFileHandler('logs/backend.log',maxBytes=104857600,backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Backend Logger')


from app import models, routes
from app.admin import AdminView

routes.routes(app=app, db=db, socketio=socketio, logger=app.logger or logger)
admin_config.add_view(AdminView(models.Feedback, db.session))

