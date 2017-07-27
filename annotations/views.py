import logging

from annotations.views_annotation import annotation_create, annotation_get
from annotations.views_annotation_set import (
    annotation_set_create, annotation_set_get
)
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
from rest_framework.permissions import IsAuthenticatedOrReadOnly


logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@authentication_classes((SessionAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticatedOrReadOnly,))
def annotation(request: HttpRequest) -> JsonResponse:
    """Get or create an annotation.

    Args:
        request:
            Incoming HTTP request

    Returns:
        JSON response.
    """

    if request.method == 'GET':
        return annotation_get(request)

    return annotation_create(request)
