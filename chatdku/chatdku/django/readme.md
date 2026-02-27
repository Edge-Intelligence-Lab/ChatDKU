# 1. ChatDKU : The Backend

## 1.1. <u>Table of Contents</u>

- [1. ChatDKU : The Backend](#1-chatdku--the-backend)
  - [1.1. Table of Contents](#11-table-of-contents)
- [2. Django Backend](#2-django-backend)
    - [2.0.1. Requirements](#201-requirements)
    - [2.0.2. Project Structure](#202-project-structure)
    - [2.0.3. Running the Project](#203-running-the-project)
      - [2.0.3.1. Setting up Environment Variables](#2031-setting-up-environment-variables)
      - [2.0.3.2. Step 1: Check for migrations](#2032-step-1-check-for-migrations)
      - [2.0.3.3. Step 2: Apply Migrations](#2033-step-2-apply-migrations)
      - [2.0.3.4. Step 3 (Optional): Create Super User](#2034-step-3-optional-create-super-user)
      - [2.0.3.5. Step 4: Running the Backend](#2035-step-4-running-the-backend)
      - [2.0.3.6. Running Celery](#2036-running-celery)
    - [2.0.4. Production](#204-production)
      - [2.0.4.1. Running Backend server](#2041-running-backend-server)
      - [2.0.4.2. Running Celery](#2042-running-celery)
    - [2.0.5. Closing the Backend](#205-closing-the-backend)
    - [2.0.6. Additional Information](#206-additional-information)
      - [2.0.6.1. **Admin User**](#2061-admin-user)
      - [2.0.6.2. **Viewing Routes**](#2062-viewing-routes)




# 2. Django Backend

<h4> Welcome to the Django Backend of ChatDKU! The Django Backend supplements the Flask backend previously used in ChatDKU. It features all the funcitonality from the prior system alongside some additional features. 

Websocket funcionality, however, is not translated into this current version. `speech-to-text` runs on flask backend.
</h4>

----
### 2.0.1. Requirements

The current version of ChatDKU uses the following packages for Django Backend. You can download the packages via [pyproject.toml][def]

### 2.0.2. Project Structure
```
chatdku_django/
├── chat/
├── chatdku_django/
├── core/
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

### 2.0.3. Running the Project
When running the project, make sure you are in the same dir as `manage.py`.

#### 2.0.3.1. Setting up Environment Variables
To run the backend, make sure you have `.env` file in the same directory as `manage.py`
```bash
    chatdku_django/
    ├── manage.py
    ├── .env     
```
Make sure your `.env` file contains the following:

```bash
SECRET_KEY="change-me"
FIELD_ENCRYPTION_KEY="change-me"
UPLOAD_PATH="./data/uploads"
WHISPER_MODEL_URI="http://localhost:5000"

#DB
USERNAME_DB="chatdku_user"
NAME_DB="chatdku_db"
PASSWORD_DB="change-me"
HOST_DB="localhost"
PORT_DB="5432"

MEDIA_ROOT="./data/uploads"

#Redis
REDIS_PASSWORD="change-me"
REDIS_HOST="127.0.0.1"

#Locust
UID="chatdku_admin"
DISPLAY_NAME="Admin"
HOST="http://localhost:8000"
LOCUST_PATH=".venv/bin/locust" # Use your env for this part. Example: venv/bin/locust

#Email
EMAIL_HOST="smtp.example.com"
EMAIL_PORT=25
EMAIL_USE_TLS=True
EMAIL_HOST_USER="chatdku@example.com"
# EMAIL_HOST_PASSWORD=""
EMAIL_TO='["abc@xyz.com","def@ghi.com"]'

LLM_API_KEY="change-me"
```
#### 2.0.3.2. Step 1: Check for migrations

```bash
python manage.py makemigrations
```
This will create new migration files based on changes in the model. 
> ❗ Make sure to run this command for every change you make in models.

#### 2.0.3.3. Step 2: Apply Migrations
```bash 
python manage.py migrate
```
This will apply all the pending migrations to the database

#### 2.0.3.4. Step 3 (Optional): Create Super User
```bash
python manage.py createsuperuser
```
This will create a superuser for the project. For ChatDKU, this step is **not** required since it already has a superuser.

#### 2.0.3.5. Step 4: Running the Backend
```bash
python manage.py runserver <port>
```
This will run the server in port `<port>`. The default port for django is `8000`.
If you use the Docker Compose `django` profile, Django runs on port `8020` in the container and is exposed on host port `8001` by default.

> **Note**: This is for development only. To view for production, check [this](#production)

Once you run the sever, you can view it via `<server ip>:<port>`. Go to `/admin` route to check the **admin dashboard**.

#### 2.0.3.6. Running Celery
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

### 2.0.4. Production

#### 2.0.4.1. Running Backend server
Chatdku uses gunicorn in addition to apache to run the backend server. To run gunicorn server use

```bash
nohup gunicorn -b <server ip>:<port> chatdku_django.wsgi:application --timeout <timeout> --workers <workers> --threads <threads> --preload &

```
The current apache configuration supports `8009` as the port.
- `--timeout` defines the timeout time for the server (in seconds).
- `--workers` define the number of worker for the backend (int).
- `--nohup`: logs are saved in `nohup.out` file. To inspect it, run
- `--threads` : define the number of threads (int).

All in all, this is the current configuration for production:

```bash
nohup gunicorn -b 0.0.0.0:8000 chatdku_django.wsgi:application --timeout 500 --workers 8 --threads 6 --preload &
```

To view live logs, you can use
```bash
tail -f nohup.out
```
Besides, logs are also saved in `log/chatdku.log` file. 



#### 2.0.4.2. Running Celery
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

### 2.0.5. Closing the Backend

After every little change, it order to deploy the backend, we will need to stop it. In order to stop the backend, you can use this script:

```bash
sudo kill -9 $(lsof -t -i : <:port>)

```

For example, this is how we would currently close the backend:

```bash

sudo kill -9 $(lsof -t -i :8000)

```

To redeploy, you can refer [here](#production). You **do not** need to redeploy **Celery**

### 2.0.6. Additional Information
- ChatDKU is using `PostgreSQL` to track files and users. We `DO NOT` store raw `netid` in the database. Instead, they are hashed using `SHA-256`. To view database port, run
```bash
sudo ss -tulnp | grep postgres
```
- The User folders are random.

#### 2.0.6.1. **Admin User**

We implement the Django admin pannel inorder to make model easily accessible for the devs as well as other admin. The devs are automatically logged into the account once they view the main site. As for other users, they can use the following details to access the dashboard

**Username**: chatdku_admin

**Password**: (set by your deployment)

The current dashboard URL depends on your deployment.

#### 2.0.6.2. **Viewing Routes**

ChatDKU implements the up-to-date version of [OpenAPI](https://www.openapis.org/) to document the views present in the project. Devs can view the API documentation at `/doc/schema/view` on your deployment.




[def]: ../../pyproject.toml
