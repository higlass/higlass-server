from django.conf.urls import url, include
from tilesets import views
from rest_framework.routers import DefaultRouter
from rest_framework_swagger.views import get_swagger_view

schema_view = get_swagger_view(title='Pastebin API')
# Create a router and register our viewsets with it.
router = DefaultRouter()

router.register(r'tilesets', views.TilesetsViewSet)
#router.register(r'users', views.UserViewSet)


# The API URLs are now determined automatically by the router.
# Additionally, we include the login URLs for the browsable API.
urlpatterns = [
    url(r'^schema', schema_view),
    url(r'^tiles/$', views.tiles),
    url(r'^tileset_info/$', views.tileset_info),
    url(r'^', include(router.urls)),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^users/$', views.UserList.as_view()),
    url(r'^users/(?P<pk>[0-9]+)/$', views.UserDetail.as_view())
]
