#!/usr/bin/env python3
# FIXME: Purge API key from the history of this file

### TODO: Create multiple app objects in advance, lock the app object for each user, and reset the app object when the user is not using it.
###TODO: Add limiter to prevent Ddos attack. Can use flask-limiter, with ePPn from Shibboleth to limit unique identity. If not possible, restricy general question over a specific IP to a specific number.


import eventlet
eventlet.monkey_patch()

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from models import Feedback

from extentions import db, migrate,admin
from admin_setup import AdminView

import dspy
import logging

from werkzeug.middleware.proxy_fix import ProxyFix

from chatdku.setup import setup, use_phoenix
from chatdku.core.agent import Agent, CustomClient
from routes import routes

app = Flask(__name__)
app.wsgi_app=ProxyFix(app.wsgi_app,x_proto=1,x_host=1) #Let flask know it is behind a reverse proxy.

CORS(app, origins=["https://chatdku.dukekunshan.edu.cn"])
socketio = SocketIO(app, cors_allowed_origins=["https://chatdku.dukekunshan.edu.cn"],async_mode="eventlet") #Socket IO to receive audio 


setup()
use_phoenix()
llama_client = CustomClient()
dspy.settings.configure(lm=llama_client)
agent = Agent(max_iterations=5, streaming=True, get_intermediate=False)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app.config["SQLALCHEMY_DATABASE_URI"]="sqlite:///./database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db.init_app(app)
migrate.init_app(app, db)
admin.init_app(app)
admin.add_view(AdminView(Feedback,db.session))


routes(app=app,db=db,socketio=socketio,logger=logger)



# NOTE: gunicorn doesn't use if __name__ == "__main__" . SO it can be commented out. For development it can be uncommented and used with `python agent_app.py`

if __name__ == "__main__":
     setup()
     use_phoenix()
     llama_client = CustomClient()
     dspy.settings.configure(lm=llama_client)
     agent = Agent(max_iterations=1, streaming=True, get_intermediate=False)

     socketio.run(app=app,host="0.0.0.0", port=8000)
    # NOTE: Might want to make it easier to change the port

