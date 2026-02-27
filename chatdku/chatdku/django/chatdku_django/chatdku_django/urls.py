"""
URL configuration for chatdku_django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
import chat.urls
import core
import core.urls
from django.conf.urls.i18n import i18n_patterns
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
import chat

from rest_framework.permissions import IsAdminUser

#URL pattern for language (en/zh-hans)
urlpatterns=[
    path('i18n/',include("django.conf.urls.i18n"))
]

urlpatterns += i18n_patterns(

    path('admin/', admin.site.urls),

)
#URL for ChatDKU django apps
urlpatterns+=[
    path("user/",include(core.urls)),
    path("api/",include(chat.urls))

]
#drf spectacular routes
urlpatterns+= [
    path('', include('django_prometheus.urls')),
    path('doc/schema/', SpectacularAPIView.as_view(permission_classes=[IsAdminUser]), name='schema'),
    path('doc/schema/view/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # path('doc/schema/redoc/', SpectacularRedocView.as_view(url_name='schema',), name='redoc'),
]