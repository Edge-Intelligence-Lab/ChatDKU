# NOTE: This is a temporary fix to socket shutdown problem
import eventlet
eventlet.monkey_patch()

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO


import logging

from routes import socket_route
app = Flask(__name__)

CORS(app)
socketio = SocketIO(app,async_mode="eventlet") #Socket IO to receive audio 

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

socket_route(socketio=socketio,logger=logger)



# NOTE: gunicorn doesn't use if __name__ == "__main__" . SO it can be commented out. For development it can be uncommented and used with `python agent_app.py`

if __name__ == "__main__":
     socketio.run(app=app,host="0.0.0.0", port=8002)
    # NOTE: Might want to make it easier to change the port

