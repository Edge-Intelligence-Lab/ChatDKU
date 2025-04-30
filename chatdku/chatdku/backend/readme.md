# About Backend

### This is the updated backend for ChatDKU. This current branch has 2 versions of the backend:

1. `agent_app.py`: This version of backend **Does Not** have `speech-to-text` built into it.
2. `agent_stt_app.py`: This version of backend **Does** support `speech-to-text`.

## Backend Layout
- `admin_setup.py`: Views for Admin route
- `routes.py`: All the routes for ChatDKU
-  `models.py`: SQL-Alchemy based ORM for ChatDKU
-  `extentions.py`: Import references
-  `whsiper_model.py`: Whisper model
-   `agent_app.py` / `agent_stt_app.py` / `agent_app_parallel.py`: Flask app file.

## Using the backend

### Activating environment

Firstly, clone the branch and download the dependencies from `pyproject.toml`. It is advised to have a virtual environment using:
```bash 
python -m venv .venv 
```
To activate the environment,

On Windows:
```bash
. .venv/Scripts/activate
```

On Linux/Mac
```bash
. .venv/bin/activate
```

### **Setting up Database**

ChatDKU uses a database to store user feedback data to enhance future responses. Our database **Does Not** contain any personal information. 

The first step is to create a database to store `feedback` data.
```bash
flask db upgrade
```

This should create a database table for you. You can access the database via `/instance/database.db` or through the admin route.
In order to access the database via admin, go to `<server:port>/admin`. However, make sure you have your `Flask` application running.



### Running the Flask app

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

### Running the Whisper Model
ChatDKU uses OpenAI's Whisper model for speech-to-text. You can find the details about the model via [whisper-base](https://huggingface.co/openai/whisper-base).

The current version of speech-to-text uses `whisper-base` model.

To run the model, run

```bash
gunicorn -w 1 -b <server:port> whisper_model:app 
```
This should run your `whisper` model in a specific port.
**Note**: depending on your server port, update the `routes.py` file.

---
