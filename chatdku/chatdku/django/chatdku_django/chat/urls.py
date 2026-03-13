from django.urls import path,include
from django.views.decorators.csrf import csrf_exempt
from . import views
from rest_framework.routers import DefaultRouter

router=DefaultRouter()
router.register(r'c',views.SessionViewSet,basename='c')

urlpatterns=[
    path('chat',csrf_exempt(views.ChatView.as_view()),name="chat"),
    path("feedback",csrf_exempt(views.FeedbackView.as_view()),name="feedback"),
    path('',include(router.urls))
]
