### This is the updated backend for ChatDKU. This current branch has 2 versions of backend:

1. `agent_app.py`: This version of backend **Does Not** have `speech-to-text` built into it.
2. `agent_stt_app.py`: This version of backend **Does** support `speech-to-text`.


## Using the backend

### **Setting up Database**


Firstly clone the branch and download the dependencies from `pyproject.toml`.

Then, set up the database using:
```bash
flask db upgrade
```

This should create database table for you. In order to access the database, go to `<server:port>/admin`

### Running Flask app

We are using `gunicorn` to deploy our backend. If you are running `agent_stt_app.py` run this script:

```bash
gunicorn --worker-class eventlet -w 1 -b <server:port> agent_stt_app:app

```
This should deploy your backend on `http`. If you want to deploy it on `https` run this script:

```bash
gunicorn --worker-class eventlet -w 1 -b <server:port> \
--certfile certs/dev.crt \
--key certs/dev.key \
agent_stt_app:app
```

If you are running `agent_app` on `http` run this:
```bash
gunicorn -w 1 -b <server:port> agent_app:app
```
For `https`, run this:

```bash
gunicorn -w 1 -b <server:port> \
--certfile certs/dev.crt \
--key certs/dev.key \
agent_app:app
```

**Note**: Make sure to export the SSL certificate and place it as trusted in your web-browser to access `HTTPS`. 

---
