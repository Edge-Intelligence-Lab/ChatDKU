from django.urls import path
from . import views


urlpatterns=[
    path("upload",views.UploadView.as_view(),name="upload"),
    path("health",views.HealthView.as_view(),name="health")
]