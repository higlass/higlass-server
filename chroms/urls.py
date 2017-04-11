from django.conf.urls import url
from chroms import views


# The API URLs are now determined automatically by the router.
# Additionally, we include the login URLs for the browsable API.
urlpatterns = [
    url(r'^chrom-sizes/$', views.sizes),
]
