# **Django Backend For Chatdku**

## About 
The Django Backend supplements the Flask backend previously used in ChatDKU. It features all the funcitonality from the prior system along side some additional features.

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
    "redis~=5.2.1"
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
- `chat/` is the chatapp for query and feedback.
- `core/` is the user app for everything related to the 
user.
- `*/views.py` contains routes for respective apps.
- `*/middleware.py` checks for netid in the header.
- `*/models.py` model for each app.
- `*/admin.py` handles admin for the respective app
- `chatdku_django/celery.py` uses `celery` for automation. Check [celery_docs](https://docs.celeryq.dev/en/latest/django/first-steps-with-django.html) for using it.
- `*/tasks.py` contains celery tasks for each app.
- `locustfile.py` contains load test script for the app.
- `chat/mail.py` contains mailing feature for app. Currently it is configured to send email per error and weekly email for load test results and feedback.
 
> You can check `chatdku_django/urls.py` for all the routes used in this project. 

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
SECRET_KEY= <secret key>
FIELD_ENCRYPTION_KEY= <encryption key> # Has not been used 
UPLOAD_PATH=<doc upload path>
WHISPER_MODEL_URI="http://10.200.14.82:8002"

#DB
USERNAME_DB="chatdku_user"
NAME_DB="chatdku_db"
PASSWORD_DB= <dbpassword>
HOST_DB="localhost"
PORT_DB="5432"

MEDIA_ROOT= <Media Root>

#Redis
REDIS_PASSWORD= <password>
REDIS_HOST="127.0.0.1"

#Locust
UID=<testing netid>
DISPLAY_NAME= <testing Display Name>
HOST= <host>
LOCUST_PATH= <.venv_path/locust>

#Email
EMAIL_HOST= <duke smtp>
EMAIL_PORT= <email port>
EMAIL_USE_TLS = True
EMAIL_HOST_USER= <host email>
# Sender Email should be a string of lists. Eg: '["abc.xyz.com","abc.example.com"]' 
EMAIL_TO= <sender email> 
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
All the Celery Configurations are already set up in the project itself in [`celery.py`](./chatdku_django/chatdku_django/celery.py) and [`settings.py`](./chatdku_django/chatdku_django/settings.py). The project uses Celery to:
- Schedule file and embedding cleaning
- Schedule daily and weekly load test
- Schedule weekly loadtest email / error emails

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
- `--timeout` defines the timeout time for the server.
- `--workers` define the number of worker for the backend.
- `--nohup`: logs are saved in `nohup.out` file. To inspect it, run
```bash
tail -f nohup.out
```
Besides, logs are also saved in `log/chatdku.log` file. 

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







