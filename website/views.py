import subprocess
import pyppeteer
import asyncio
import logging
import os
import os.path as op
from pyppeteer import launch
import tempfile

import tilesets.models as tm

import higlass_server.settings as hss

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest, HttpResponse, \
    HttpResponseNotFound, HttpResponseBadRequest

logger = logging.getLogger(__name__)

def link(request):
    '''Generate a small page containing the metadata necessary for
    link unfurling by Slack or Twitter. The generated page will
    point to a screenshot of the rendered viewconf. The page will automatically
    redirect to the rendering so that if anybody clicks on this link
    they'll be taken to an interactive higlass view.

    The viewconf to render should be specified with the d= html parameter.

    Args:
        request: The incoming http request.
    Returns:
        A response containing an html page with metadata
    '''
    # the uuid of the viewconf to render
    uuid = request.GET.get('d')

    if not uuid:
        # if there's no uuid specified, return an empty page
        return HttpResponseNotFound('<h1>No uuid specified</h1>')

    try:
        obj = tm.ViewConf.objects.get(uuid=uuid)
    except ObjectDoesNotExist:
        return HttpResponseNotFound('<h1>No such uuid</h1>')

    # the url for the thumnbail
    thumb_url=f'{request.scheme}://{request.get_host()}/thumbnail/?d={uuid}'

    # the page to redirect to for interactive explorations
    redirect_url=f'{request.scheme}://{request.get_host()}/app/?config={uuid}'

    # Simple html page. Not a template just for simplicity's sake.
    # If it becomes more complex, we can make it into a template.
    html = f"""<html>
<meta charset="utf-8">
<meta name="author" content="Peter Kerpedjiev, Fritz Lekschas, Nezar Abdennur, Nils Gehlenborg">
<meta name="description" content="Web-based visual exploration and comparison of Hi-C genome interaction maps and other genomic tracks">
<meta name="keywords" content="3D genome, genomics, genome browser, Hi-C, 4DN, matrix visualization, cooler, Peter Kerpedjiev, Fritz Lekschas, Nils Gehlenborg, Harvard Medical School, Department of Biomedical Informatics">
<meta itemprop="name" content="HiGlass">
<meta itemprop="description" content="Web-based visual exploration and comparison of Hi-C genome interaction maps and other genomic tracks">
<meta itemprop="image" content="{thumb_url}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@higlass_io">
<meta name="twitter:title" content="HiGlass">
<meta name="twitter:description" content="Web-based visual exploration and comparison of Hi-C genome interaction maps and other genomic tracks">
<meta name="twitter:creator" content="@flekschas"><meta name="twitter:image:src" content="{thumb_url}">
<meta property="og:title" content="HiGlass"/>
<meta property="og:description" content="Web-based visual exploration and comparison of Hi-C genome interaction maps and other genomic tracks"/>
<meta property="og:type" content="website"/><meta property="og:url" content="https://higlass.io"/>
<meta property="og:image" content="{thumb_url}"/>
<meta name="viewport" content="width=device-width,initial-scale=1,shrink-to-fit=no">
<meta name="theme-color" content="#0f5d92">
    <body></body>
    <script>
        window.location.replace("{redirect_url}");
    </script>
    </html>
    """

    return HttpResponse(html)

def thumbnail(request: HttpRequest):
    '''Retrieve a thumbnail for the viewconf specified by the d=
    parameter.

    Args:
        request: The incoming request.
    Returns:
        A response of either 404 if there's no uuid provided or an
        image containing a screenshot of the rendered viewconf with
        that uuid.
    '''
    uuid = request.GET.get('d')

    base_url = f'{request.scheme}://localhost/app/'

    if not uuid:
        return HttpResponseNotFound('<h1>No uuid specified</h1>')

    if '.' in uuid or '/' in uuid:
        # no funny business
        logger.warning('uuid contains . or /: %s', uuid)
        return HttpResponseBadRequest("uuid can't contain . or /")

    if not op.exists(hss.THUMBNAILS_ROOT):
        os.makedirs(hss.THUMBNAILS_ROOT)

    output_file = op.abspath(op.join(hss.THUMBNAILS_ROOT, uuid + ".png"))
    thumbnails_base = op.abspath(hss.THUMBNAILS_ROOT)

    if output_file.find(thumbnails_base) != 0:
        logger.warning('Thumbnail file is not in thumbnail_base: %s uuid: %s',
                     output_file, uuid)
        return HttpResponseBadRequest('Strange path')

    if not op.exists(output_file):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            screenshot(
                base_url,
                uuid,
                output_file))
        loop.close()

    with open(output_file, 'rb') as file:
        return HttpResponse(
            file.read(),
            content_type="image/jpeg")

async def screenshot(
    base_url: str,
    uuid: str,
    output_file: str
):
    '''Take a screenshot of a rendered viewconf.

    Args:
        base_url: The url to use for rendering the viewconf
        uuid: The uuid of the viewconf to render
        output_file: The location on the local filesystem to cache
            the thumbnail.
    Returns:
        Nothing, just stores the screenshot at the given location.
    '''
    browser = await launch(
        headless=True,
        args=['--no-sandbox'],
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False
    )
    url = f'{base_url}?config={uuid}'
    page = await browser.newPage()
    await page.goto(url, {
        'waitUntil': 'networkidle0',
    })
    await page.screenshot({'path': output_file})
    await browser.close()
