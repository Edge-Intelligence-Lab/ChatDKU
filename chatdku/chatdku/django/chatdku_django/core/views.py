from rest_framework.decorators import api_view 
from rest_framework.response import Response
from core.models import UploadedFile
from django.contrib.auth import get_user_model
import os
import uuid
from django.utils.timezone import now
from dotenv import load_dotenv
from core.serializers import UploadFileSerializer
from django.core.files.storage import default_storage

import logging
logger=logging.getLogger(__name__)


User=get_user_model()
load_dotenv()



ALLOWED_EXTENSIONS = ['.pdf']

def allowed_file(filename):
    return filename.lower().endswith(tuple(ALLOWED_EXTENSIONS))

@api_view(['POST'])
def upload(request):
    try:
        serializer = UploadFileSerializer(data=request.FILES)

        if not serializer.is_valid():
            return Response(serializer.errors,status=400)

        uploaded_file=serializer.validated_data["file_"]

    
        filename = f"{uuid.uuid4()}.pdf"

        folder_path = os.getenv("UPLOAD_PATH", "/datapool/uploads")
        user_folder=request.user.folder

        os.makedirs(folder_path, exist_ok=True)
        user_folder_path=os.path.join(folder_path,user_folder)
        os.makedirs(user_folder_path,exist_ok=True)
        file_path = os.path.join(user_folder_path,filename)

        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        record = UploadedFile(filename=filename, user=request.user, uploaded_time=now())
        record.save()

        return Response({"message": "File uploaded successfully"}, status=201)
    except Exception as e:
        return Response({"error":str(e)})
