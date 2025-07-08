from rest_framework.decorators import api_view, parser_classes 
from rest_framework.response import Response
from core.models import UploadedFile
from django.contrib.auth import get_user_model
import os
import uuid
from django.utils.timezone import now
from dotenv import load_dotenv
from core.serializers import UploadFileSerializer
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from chatdku.backend.user_data_interface import update
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
import json
from .utils import slugify

import logging
logger=logging.getLogger(__name__)


User=get_user_model()
load_dotenv()



ALLOWED_EXTENSIONS = ['.pdf']

def allowed_file(filename):
    return filename.lower().endswith(tuple(ALLOWED_EXTENSIONS))

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload(request):
    try:
        serializer = UploadFileSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors,status=400)

        uploaded_file=serializer.validated_data["file_"]

    
        filename = f"{slugify(os.path.splitext(uploaded_file.name)[0])}.pdf"
        print(filename)

        user_folder=request.user.folder

        user_folder_path = os.path.join(settings.MEDIA_ROOT, user_folder)
        os.makedirs(user_folder_path, exist_ok=True)
        file_path = os.path.join(user_folder, filename)  # relative path only

        full_user_folder_path = os.path.join(settings.MEDIA_ROOT, user_folder)
        os.makedirs(full_user_folder_path, exist_ok=True)

        path=default_storage.save(file_path,uploaded_file)
        saved_name=os.path.basename(path)
        record = UploadedFile(filename=saved_name, user=request.user, uploaded_time=now())
        record.save()

    # Updating Chunks
        netid=request.netid
        print(netid)
        user_folder_path_json=os.path.join(settings.MEDIA_ROOT, user_folder)
        json_path = os.path.join(user_folder_path_json, "data_state.json")
        os.makedirs(user_folder_path, exist_ok=True)
        if not os.path.exists(json_path):
            with open(json_path, "w") as f:
                json.dump({}, f)
        print("uploading")
        update(data_dir=user_folder_path_json,user_id=str(netid))
        print("uploaded")

        return Response({"message": "File uploaded successfully"}, status=201)
    except Exception as e:
        return Response({"error":str(e)})
