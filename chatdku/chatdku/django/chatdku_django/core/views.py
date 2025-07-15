from rest_framework.decorators import api_view, parser_classes 
from rest_framework.response import Response
from core.models import UploadedFile
from django.contrib.auth import get_user_model
import os
from core.set_enqueue import enqueue_user_task
from django.utils.timezone import now
from dotenv import load_dotenv
from core.serializers import UploadFileSerializer
from django.core.files.storage import default_storage
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings


from core.tasks import update_user_chroma
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
            return Response(serializer.errors, status=400)

        uploaded_file = serializer.validated_data["file_"]
        filename = f"{slugify(os.path.splitext(uploaded_file.name)[0])}.pdf"

        user_folder = request.user.folder
        relative_path = os.path.join(user_folder, filename)  # Relative path for default_storage
        full_user_folder_path = os.path.join(settings.MEDIA_ROOT, user_folder)  # Absolute path

        os.makedirs(full_user_folder_path, exist_ok=True)
        saved_path = default_storage.save(relative_path, uploaded_file)
        saved_name = os.path.basename(saved_path)

        UploadedFile.objects.create(
            filename=saved_name,
            user=request.user,
            uploaded_time=now()
        )

        # File upload queue with Redis and celery
        netid = request.netid
        enqueue_user_task(netid, user_folder_path=full_user_folder_path)
        logger.info(f"Enqueued task for user: {netid}")

        return Response({"message": "File uploaded successfully"}, status=201)

    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
def get_user_files(request):
    try:
        docs=list(request.user.files.values_list("filename",flat=True))
        netid=request.netid
        return Response({
            "netid":netid,
            "document":docs
        },status=200)
    except Exception as e:
        return Response({"error":{str(e)}},status=500)