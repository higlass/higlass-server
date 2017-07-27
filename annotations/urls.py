from django.conf.urls import url
from annotations import views


urlpatterns = [
    url(r'^annotation/$', views.annotation),
]
