from django.conf.urls import url, include
from website import views

# The API URLs are now determined automatically by the router.
# Additionally, we include the login URLs for the browsable API.
urlpatterns = [
    #url(r'^schema', schema_view),
    url(r'^link/$', views.link),
    url(r'^l/$', views.link),
    url(r'^thumbnail/$', views.thumbnail),
    url(r'^t/$', views.thumbnail)
]
