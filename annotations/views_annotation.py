import logging

from annotations.exceptions import TransactionFailed
from annotations.models import Locus, Pattern, Annotation
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from rest_framework.exceptions import ParseError
from tilesets.models import Tileset


logger = logging.getLogger(__name__)


def annotation_create(request: HttpRequest) -> JsonResponse:
    """Create an annotation.

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
                loci = request.data.get('loci', [])
                description = request.data.get('description', None)
            except AttributeError as e:
                raise TransactionFailed('Mandatory entry is missing.', 400)
            except ParseError as e:
                raise TransactionFailed('Post data is broken.', 400)

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
                    raise TransactionFailed(
                        'Locus broken. Mandatory entries are missing.',
                        400
                    )

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
                    raise TransactionFailed('Tileset entry is missing.', 400)

                try:
                    tileset = Tileset.objects.get(uuid=tileset_uuid)
                except Tileset.DoesNotExist:
                    raise TransactionFailed(
                        'Tileset object is not found.', 404
                    )

                # Get or create pattern
                pattern, _ = Pattern.objects.get_or_create({
                    'locus': locus_obj,
                    'tileset': tileset,
                    'zoom_out_level': loci.get('zoom_out_level', None)
                })

                annotation.patterns.add(pattern)

            return JsonResponse({'uuid': annotation.uuid})

    except TransactionFailed as e:
        return JsonResponse({'error': e.message}, status=e.status_code)

    except Exception as e:
        return JsonResponse({'error': e.message}, status=500)


def annotation_get(request: HttpRequest) -> JsonResponse:
    """Get an annotation.

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
        annotation = (
            Annotation
            .objects
            .get(**kwargs)
            .prefetch_related('patterns__locus__tileset')
        )
    except Annotation.DoesNotExist:
        return JsonResponse({
            'error': 'Annotation not found',
        }, status=404)

    patterns = []
    for pattern in annotation.patterns.all():
        pattern.append({
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

    return JsonResponse({
        'description': annotation.description,
        'patterns': patterns,
        'slug': annotation.slug,
        'uuid': annotation.uuid,
    })
