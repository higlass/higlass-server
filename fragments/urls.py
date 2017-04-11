from django.conf.urls import url
from fragments import views


# The API URLs are now determined automatically by the router.
# Additionally, we include the login URLs for the browsable API.
urlpatterns = [
    url(r'^fragments_by_loci/$', views.fragments_by_loci),
    url(r'^fragments_by_chr/$', views.fragments_by_chr),
    url(r'^loci/$', views.loci),
]
