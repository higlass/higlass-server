from django.conf.urls import url, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    url(r'^login/$', auth_views.login, {'template_name': 'higlass/login.html'}, name='login'),
    url(r'^logout/$', auth_views.logout, name='logout'),
]
