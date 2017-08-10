import logging

from django.http import HttpRequest, JsonResponse
from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication
)
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes
)
from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from rest_framework.permissions import IsAuthenticated


logger = logging.getLogger(__name__)

AUTH_CLASSES = (
    SessionAuthentication, BasicAuthentication, JSONWebTokenAuthentication
)


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes((IsAuthenticated,))
def current(request: HttpRequest) -> JsonResponse:
    """Verify authentication and get current user data for initializing
    HiGlassApp.

    Args:
        request:
            Incoming HTTP request

    Returns:
        JSON response.
    """

    return JsonResponse({
        'username': request.user.username,
        'email': request.user.email
    })
