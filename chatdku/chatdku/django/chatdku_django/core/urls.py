from django.urls import path
from . import views


urlpatterns=[
    path("upload",views.upload,name="upload"),
    path("user_files",views.get_user_files,name="get_user_files")
]