from django.urls import path
from . import views

urlpatterns=[
    path('chat',views.chat,name="chat"),
    path("feedback",views.save_feedback,name="feedback"),
]