from django.urls import path,include
from . import views
from rest_framework.routers import DefaultRouter

router=DefaultRouter()
router.register(r'c',views.SessionViewSet,basename='c')

urlpatterns=[
    path('chat',views.chat,name="chat"),
    path("feedback",views.save_feedback,name="feedback"),
    path('get_session',views.get_session,name="get_session"),
    path('',include(router.urls))
]
