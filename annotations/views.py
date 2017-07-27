import logging

from annotations.models import Locus, Pattern, Annotation, AnnotationSet
from django.db import transaction
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
from rest_framework.exceptions import ParseError
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from tilesets.models import Tileset


logger = logging.getLogger(__name__)


@transaction.atomic
def annotation_create(request: HttpRequest) -> JsonResponse:
    """Create an annotation.

    Args:
        request:
            Incoming HTTP request

    Returns:
        JSON response.
    """

    # Extract mandatory props
    try:
        loci = request.data.get('loci', [])
        description = request.data.get('description', None)
    except AttributeError as e:
        return JsonResponse({
            'error': 'Mandatory entry is missing.',
            'errorDetails': str(e)
        }, status=400)
    except ParseError as e:
        return JsonResponse({
            'error': 'Body is broken.',
            'errorDetails': str(e)
        }, status=400)

    # Extract optional props
    try:
        slug = request.data.get('slug', None)
    except Exception:
        slug = None

    # Check of any loci are passed
    if len(loci) == 0:
        return JsonResponse({
            'error': 'No loci specified.'
        }, status=400)

    # Create annotation
    annotation = Annotation.objects.create({
        'description': description,
        'slug': slug
    })

    for locus in loci:
        # Get or create locus
        try:
            chrom1 = loci['chrom1']
            start1 = loci['start1']
            end1 = loci['end1']
            coords = loci['coords']
        except KeyError:
            return JsonResponse({
                'error': 'Locus broken. Mandatory entry is missing.'
            }, status=400)

        locus_obj, _ = Locus.objects.get_or_create({
            'chrom1': chrom1,
            'start1': start1,
            'end1': end1,
            'chrom2': loci.get('chrom2', None),
            'start2': loci.get('start2', None),
            'end2': loci.get('end2', None),
            'coords': coords,
        })

        # Get tileset
        try:
            tileset_uuid = loci['tileset']
        except Tileset.DoesNotExist:
            return JsonResponse({
                'error': 'Tileset is missing.'
            }, status=400)

        try:
            tileset = Tileset.objects.get(uuid=tileset_uuid)
        except Tileset.DoesNotExist:
            return JsonResponse({
                'error': 'Tileset is not found.'
            }, status=404)

        # Get or create pattern
        pattern, _ = Pattern.objects.get_or_create({
            'locus': locus_obj,
            'tileset': tileset,
            'zoom_out_level': loci.get('zoom_out_level', None)
        })

        annotation.patterns.add(pattern)

    return JsonResponse({
        'uuid': annotation.uuid
    })


def annotation_get(request: HttpRequest) -> JsonResponse:
    """Get an annotation.

    Args:
        request:
            Incoming HTTP request

    Returns:
        JSON response.
    """

    try:
        uuid = request.GET.get('precision', None)
    except ValueError:
        uuid = None

    try:
        slug = request.GET.get('precision', None)
    except ValueError:
        slug = None

    if not uuid and not slug:
        return JsonResponse({
            'error': 'Either specify a UUID or a slug.',
        }, status=400)

    kwargs = {}
    if uuid:
        kwargs['uuid'] = uuid
    if slug:
        kwargs['slug'] = slug

    try:
        annotation = Annotation.objects.get(**kwargs)
    except Annotation.DoesNotExist:
        return JsonResponse({
            'error': 'Annotation not found',
        }, status=404)

    annotation

    return JsonResponse({
        'uuid': annotation.uuid
    })


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
