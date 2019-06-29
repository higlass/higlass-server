import subprocess
import pyppeteer
import asyncio
import logging
import os
import os.path as op
from pyppeteer import launch
import tempfile

logger = logging.getLogger(__name__)

import higlass_server.settings as hss

async def screenshot():
    browser = await launch(
    handleSIGINT=False,
    handleSIGTERM=False,
    handleSIGHUP=False
        )
    page = await browser.newPage()
    await page.goto('http://higlass.io')
    await page.screenshot({'path': '/tmp/example.png'})
    await browser.close()

from django.http import HttpResponse, HttpResponseNotFound

def link(request):
    config = request.GET.get('config')
    uuid = request.GET.get('d')

    if not uuid:
        return HttpResponseNotFound('<h1>No uuid specified</h1>')

    thumb_url=f'{request.scheme}://{request.get_host()}/thumbnail/?d={uuid}'
    redirect_url=f'{request.scheme}://{request.get_host()}/app/?config={uuid}'

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

def thumbnail(request):
    print('request:', dir(request))
    print('r', request.get_host())
    print('r', request.get_port())
    print('s', request.scheme)
    print('u', request.get_raw_uri())

    uuid = request.GET.get('d')

    base_url = f'{request.scheme}://localhost/app/'

    if not uuid:
        return HttpResponseNotFound('<h1>No uuid specified</h1>')
    if not op.exists(hss.THUMBNAILS_ROOT):
        os.makedirs(hss.THUMBNAILS_ROOT)
    output_file = op.join(hss.THUMBNAILS_ROOT, uuid + ".png")

    if not op.exists(output_file):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            screenshot(
                base_url,
                uuid,
                output_file))
        loop.close()

    with open(output_file, 'rb') as f:
        return HttpResponse(
            f.read(),
            content_type="image/jpeg")

async def screenshot(base_url, uuid, output_file):
    browser = await launch(
        headless=True,
        args=['--no-sandbox'],
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False
    )
    # print('base_url:', base_url)
    url = f'{base_url}?config={uuid}'
    # print("url:", url)
    page = await browser.newPage()
    await page.goto(url, {
        'waitUntil': 'networkidle2',
    })
    await page.screenshot({'path': output_file})
    await browser.close()