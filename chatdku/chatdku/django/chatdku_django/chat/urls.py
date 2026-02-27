from django.urls import path,include
from . import views
from rest_framework.routers import DefaultRouter

router=DefaultRouter()
router.register(r'c',views.SessionViewSet,basename='c')

urlpatterns=[
    path('chat',views.ChatView.as_view(),name="chat"),
    path("feedback",views.FeedbackView.as_view(),name="feedback"),
    path('',include(router.urls))
]
