import logging

from annotations.exceptions import TransactionFailed
from annotations.models import Annotation, AnnotationSet
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from rest_framework.exceptions import ParseError


logger = logging.getLogger(__name__)


def annotation_set_create(request: HttpRequest) -> JsonResponse:
    """Create an annotation set.

    Args:
        request:
            Incoming HTTP request

    Returns:
        JSON response.
    """

    try:
        with transaction.atomic():
            # Extract mandatory props
            try:
                annotation_uuids = request.data.get('annotations', [])
                description = request.data.get('description', None)
            except AttributeError as e:
                raise TransactionFailed('Mandatory entry is missing.', 400)
            except ParseError as e:
                raise TransactionFailed('Body is broken.', 400)

            # Extract optional props
            try:
                slug = request.data.get('slug', None)
            except Exception:
                slug = None

            # Create annotation
            annotation_set = AnnotationSet.objects.create({
                'description': description,
                'slug': slug
            })

            for annotation_uuid in annotation_uuids:
                try:
                    annotation = Annotation.objects.get(uuid=annotation_uuid)
                except Annotation.DoesNotExist:
                    return JsonResponse({
                        'uuid': annotation_set.uuid
                    })

                annotation_set.annotations.add(annotation)

            return JsonResponse({
                'uuid': annotation_set.uuid
            })

    except TransactionFailed as e:
        return JsonResponse({'error': e.message}, status=e.status_code)

    except Exception as e:
        return JsonResponse({'error': e.message}, status=500)


def annotation_set_get(request: HttpRequest) -> JsonResponse:
    """Get an annotation set.

    Args:
        request:
            Incoming HTTP request

    Returns:
        JSON response.
    """

    try:
        uuid = request.GET.get('uuid', None)
    except ValueError:
        uuid = None

    try:
        slug = request.GET.get('slug', None)
    except ValueError:
        slug = None

    try:
        fetch_patterns = request.GET.get('fetch-patterns', False)
    except ValueError:
        fetch_patterns = False

    if not uuid and not slug:
        return JsonResponse({
            'error': 'Either specify a UUID or a slug.',
        }, status=400)

    kwargs = {}
    if uuid:
        kwargs['uuid'] = uuid
    if slug:
        kwargs['slug'] = slug

    prefetch = 'annotations__patterns'
    if fetch_patterns:
        prefetch = 'annotations__patterns__locus__tileset'

    try:
        annotation_set = (
            AnnotationSet
            .objects
            .get(**kwargs)
            .prefetch_related(prefetch)
        )
    except AnnotationSet.DoesNotExist:
        return JsonResponse({
            'error': 'Annotation not found',
        }, status=404)

    annotations = []
    for annotation in annotation_set.annotations.all():
        patterns = []

        if fetch_patterns:
            for pattern in annotation.patterns.all():
                pattern.append({
                    'uuid': pattern.uuid,
                    'chrom1': pattern.locus.chrom1,
                    'start1': pattern.locus.start1,
                    'end1': pattern.locus.end1,
                    'chrom2': pattern.locus.chrom2,
                    'start2': pattern.locus.start2,
                    'end2': pattern.locus.end2,
                    'coords': pattern.locus.coords,
                    'tileset': pattern.tileset.uuid,
                    'zoomOutLevel': pattern.zoom_out_level,
                })
        else:
            for pattern in annotation.patterns.all():
                patterns.append(pattern.uuid)

        annotations.append({
            'description': annotation.description,
            'patterns': patterns,
            'slug': annotation.slug,
            'uuid': annotation.uuid,
        })

    return JsonResponse({
        'annotations': annotations,
        'description': annotation_set.description,
        'slug': annotation_set.slug,
        'uuid': annotation_set.uuid,
    })
