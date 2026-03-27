from core.models import UploadedFile, UserModel
from celery import shared_task
from django.db import transaction
from chatdku.backend.user_data_interface import update
from core.set_lock import redis_lock
from chatdku_django.celery import redis_client
import sys
import subprocess

import json

import os
import dotenv
import shutil
import logging


from chatdku.backend.user_data_interface import update

logger=logging.getLogger(__name__)

dotenv.load_dotenv()

FOLDER_PATH=os.environ.get("MEDIA_ROOT")



def remove_from_db(filename):
    try:
        with transaction.atomic():
            UploadedFile.objects.filter(filename=filename).delete()

    except Exception as e:
        logger.error(f"Failed to remove {filename} from DB: {e}")



# @shared_task
def remove_files():
    db_filenames=set(UploadedFile.objects.values_list('filename',flat=True))

    for item in os.listdir(FOLDER_PATH):
        user_path=os.path.join(FOLDER_PATH,item)

        if os.path.isdir(user_path):

            for filename in os.listdir(user_path):
                file_path=os.path.join(user_path,filename)
                try:
                    if os.path.isfile(file_path):
                        if filename in db_filenames:
                            os.remove(file_path)
                            remove_from_db(filename)

                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.warning(f'Failed to delete {file_path}: {e}')

# @shared_task
def update_user_embedding():
    try:
        query=UserModel.objects.values_list('username','folder')
        if not query:
            return "No User Found"
        user_names,user_folders=zip(*query)

        for name,folder in zip(user_names,user_folders):
            if str(name).startswith('admin'):
                continue
            else:
                try:
                    data_dir=os.path.join(FOLDER_PATH,folder)
                    update(user_id=str(name), data_dir=str(data_dir))
                except Exception as e:
                    logger.error(f"Failed to update user {name} with folder {folder}: {e}")
        return "Finished Updating"
    
    except Exception as e:
        logger.error(f"Failed to update, Error occured: {e}")

#Redis queue for user upload

@shared_task(bind=True, max_retries=5)
def update_user_chroma(self, netid):
    try:
        while (metadata := redis_client.lpop(f"queue_key:{netid}")):
            metadata_info = json.loads(metadata.decode("utf-8"))
            lock_key = metadata_info["lock_key"]

            full_data = redis_client.hgetall(f"task:{metadata_info['id']}")
            args = json.loads(full_data.get(b"args", b"[]").decode("utf-8"))
            kwargs = json.loads(full_data.get(b"kwargs", b"{}").decode("utf-8"))

            try:
                with redis_lock(lockkey=lock_key, expire=600):
                    folder = kwargs["user_folder_path"]
                    json_path = os.path.join(folder, "data_state.json")
                    os.makedirs(folder, exist_ok=True)
                    if not os.path.exists(json_path):
                        with open(json_path, "w") as f:
                            json.dump({}, f)

                    redis_client.hset(f"task:{metadata_info['id']}", "status", "running")
                    update(user_id=str(netid), data_dir=folder)
                    redis_client.hset(f"task:{metadata_info['id']}", "status", "completed")

            except Exception as e:
                logger.error(f"User {netid} task error: {e}")
                redis_client.rpush(f"queue_key:{netid}", metadata)
                self.retry(exc=e, countdown=5)

            finally:
                redis_client.delete(f"task:{metadata_info['id']}")

    finally:
        redis_client.delete(f"processing:{netid}")


# @shared_task()
# def ping_llm():
#     try:
#         ping_lm("ping")
#         ActiveLM.objects.update_or_create(id=1,defaults={"name":"primary"})

#     except Exception as e:
#         ActiveLM.objects.update_or_create(id=1,defaults={"name":"backup"})

# @shared_task(bind=True,max_retries=5)
def load_redis_task(self,script_path=None,python_bin=None):
    """
    Run a python script for ingestion
    args:
        - script_path: path for load redis (def: `ChatDKU/chatdku/ingestion/load_redis.py`)
        - python_bin: path for python executable (def: `sys.executable`)

    """

    if script_path is None:
        script_path=os.path.join(os.path.dirname(__file__),"..","..","..","ingestion","load_redis.py")
    python_exe=python_bin or sys.executable

    if not os.path.isfile(script_path):
        logger.error("[Ingestion] Script not found: %s", script_path)
        raise 



    cmd=[python_exe,script_path]
    env=os.environ.copy()

    try:
        #Run subprocess for the script and capture output, errors
        process=subprocess.run(
            cmd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=600
        )
        logger.info("[Ingestion] Load redis activated stdout: %s",process.stdout)
        return process.stdout
    except subprocess.CalledProcessError as e:
        logger.error(
            "[Ingestion] Script failed (exit %s). stdout: %s stderr: %s",
            e.returncode,
            getattr(e, "stdout", ""),
            getattr(e, "stderr", ""),
        )        
        raise self.retry(exc=e,countdown=5)
    except Exception as e:
        logger.error("[Ingestion] Error occured during Ingestion")
        raise self.retry(exc=e,countdown=5)



