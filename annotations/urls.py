from django.conf.urls import url
from annotations import views


urlpatterns = [
    url(r'^annotation/$', views.annotation),
    url(r'^annotation-sets/$', views.annotation_sets),
]
