# **Django Backend For ChatDKU**

## About 
The Django Backend supplements the Flask backend previously used in ChatDKU. It features all the funcitonality from the prior system alongside some additional features.

Websocket funcionality, however, is not translated into this current version. `speech-to-text` runs on flask backend.

## Requirements:
The current version of ChatDKU uses the following packages for Django Backend. You can download the packages via [pyproject.toml](../../pyproject.toml)

```bash
    "Django~=5.2.3",
    "django-appconf~=1.1.0",
    "django-cors-headers~=4.7.0",
    "django-cryptography~=1.1",
    "django-encrypted-model-fields~=0.6.5",
    "django-fernet-fields~=0.6",
    "django-import-export~=4.3.8",
    "djangorestframework~=3.16.0",
    "django-celery-beat~=2.8.1",
    "django_celery_results~=2.6.0",
    "celery~=5.5.3",
    "django-redis~=6.0.0",
    "pandas~=2.2.3",
    "redis~=5.2.1",
    "psycopg2-binary>=2.9.10",
    "dotenv>=0.9.9",
    "locust>=2.39.0",
    "drf-spectacular[sidecar]",

```
## Project Structure
```
chatdku_django/
├── chat/
│   ├── migrations/
│   ├── templates/email/
│   ├── admin.py
│   ├── apps.py
│   ├── mail.py
│   ├── models.py
│   ├── tests.py
│   ├── tasks.py
│   ├── urls.py
│   └── views.py
├── chatdku_django/
│   ├── asgi.py
│   ├── celery.py
│   ├── settings.py
│   ├── urls.py
│   ├── views.py
│   └── wsgi.py
├── core/
│   ├── migrations/
│   ├── admin.py
│   ├── apps.py
│   ├── middleware.py
│   ├── models.py
│   ├── serializers.py
│   ├── signals.py
│   ├── tasks.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── manage.py
├── locustfile.py

```
- [`chat/`](./chatdku_django/chat) is the chatapp for query and feedback.
- [`core/`](./chatdku_django/core) is the user app for everything related to the 
user.
- `*/views.py` contains routes for respective apps.
- `*/middleware.py` checks for netid in the header.
- `*/models.py` model for each app.
- `*/admin.py` handles admin for the respective app
- [`chatdku_django/celery.py`](./chatdku_django/chatdku_django/celery.py) uses `celery` for automation. Check [celery_docs](https://docs.celeryq.dev/en/latest/django/first-steps-with-django.html) for using it.
- `*/tasks.py` contains celery tasks for each app.
- [`locustfile.py`](./chatdku_django/locustfile.py) contains load test script for the app.
- [`chat/mail.py`](./chatdku_django/chat/mail.py) contains mailing feature for app. Currently it is configured to send email per error and weekly email for load test results and feedback.
 
> You can check [`chatdku_django/urls.py`](./chatdku_django/chatdku_django/urls.py)  for all the routes used in this project. 

## Running the Project
When running the project, make sure you are in the same dir as `manage.py`.

### Setting up Environment Variables
To run the backend, make sure you have `.env` file in the same directory as `manage.py`
```bash
    chatdku_django/
    ├── manage.py
    ├── .env     
```
Make sure your `.env` file contains the following:

```bash
SECRET_KEY=<SECRET KEY>
FIELD_ENCRYPTION_KEY=<ENCRYPTION KEY> #Is not used
UPLOAD_PATH=<Upload Path dir>
WHISPER_MODEL_URI=<WHISPER_MODEL_URI>

#DB
USERNAME_DB="chatdku_user"
NAME_DB="chatdku_db"
PASSWORD_DB=<PASSWORD>
HOST_DB="localhost"
PORT_DB="5432"

MEDIA_ROOT="/datapool/chatdku_user_storage/uploads"

#Redis
REDIS_PASSWORD= <REDIS PASSWORD>
REDIS_HOST="127.0.0.1"



#Locust
UID="chatdku_admin"
DISPLAY_NAME="Admin"
HOST='http://10.200.14.82:8000'
LOCUST_PATH=<LOCUST PATH>  #Example: "/home/abc/test/ChatDKU/chatdku/.venv/bin/locust"

#Email
EMAIL_HOST="smtp.duke.edu"
EMAIL_PORT=<:PORT>
EMAIL_USE_TLS = True
EMAIL_HOST_USER="chatdku@dukekunshan.edu.cn"
# EMAIL_HOST_PASSWORD=""
EMAIL_TO=<LIST> #Example '['abc@xyz.com','bcd@wxy.com']'


LLM_API_KEY=<:API-KEY>



```


### Step 1: Check for migrations

```bash
python manage.py makemigrations
```
This will create new migration files based on changes in the model. 
> ❗ Make sure to run this command for every change you make in models.

### Step 2: Apply Migrations
```bash 
python manage.py migrate
```
This will apply all the pending migrations to the database

### Step 3 (Optional): Create Super User
```bash
python manage.py createsuperuser
```
This will create a superuser for the project. For ChatDKU, this step is **not** required since it already has a superuser.

### Step 5: Running the Backend
```bash
python manage.py runserver <port>
```
This will run the server in port `<port>`. The default port for django is `8000`.

> **Note**: This is for development only. To view for production, check [this](#production)

Once you run the sever, you can view it via `<server ip>:<port>`. Go to `/admin` route to check the **admin dashboard**.

### Running Celery
All the Celery Configurations are already set up in the project itself in [`celery.py`](./chatdku_django/chatdku_django/celery.py) and [`settings.py`](./chatdku_django/chatdku_django/settings.py). 
To run celery for development, run
```bash
celery -A chatdku_django worker --beat -l INFO
```

> **Note**: Before running celery, make sure redis is alive.`

Since we are running redis via docker, you can check it's status using
```bash
sudo docker ps | grep redis
```
ChatDKU backend uses Redis to:
- Queue User File Upload
- Lock file chat during user upload

## Production

### Running Backend server
Chatdku uses gunicorn in addition to apache to run the backend server. To run gunicorn server use

```bash
nohup gunicorn -b <server ip>:<port> chatdku_django.wsgi:application --timeout <timeout> --workers <workers> --threads <threads> --preload &

```
The current apache configuration supports `8009` as the port.
- `--timeout` defines the timeout time for the server (in seconds).
- `--workers` define the number of worker for the backend (int).
- `--nohup`: logs are saved in `nohup.out` file. To inspect it, run
- `--threads` : define the number of threads (int).
```bash
tail -f nohup.out
```
Besides, logs are also saved in `log/chatdku.log` file. 

The current backend runs via following configuration:
```
nohup gunicorn -b <SERVER:IP:8000> chatdku_django.wsgi:application --timeout 500 --workers 8 --threads 3 --preload &
```

### Running Celery
Celery worker and beats is run using system service.You can check it via
```bash
/etc/systemd/system/chatdku_celery_beats.service
```
and
```bash
/etc/systemd/system/chatdku_celery_worker.service
```

To run it simply run:

```bash
sudo systemctl start chatdku_celery.target
```
To stop it, run:

```bash
sudo systemctl stop chatdku_celery.target
```
You can view `Celery` logs via
```bash

sudo journalctl -u chatdku_celery_worker -f
```

----
## Additional Information
- ChatDKU is using `PostgreSQL` to track files and users. We `DO NOT` store raw `netid` in the database. Instead, they are hashed using `SHA-256`. To view database port, run
```bash
sudo ss -tulnp | grep postgres
```
- The User folders are random.

### **Admin User**
**Username**: chatdku_admin

**Password**: 82f7570deb18dc2334e255085f090a07af3aad4e56c0c64d034f276ec7f77b24







