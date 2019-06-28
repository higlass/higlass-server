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

from django.http import HttpResponse

def link(request):
    config = request.GET.get('config')

    html = f"""<html>

    <body>{config}</body>
    <script>
        window.location.replace("http://www.slashdot.org");
    </script>
    </html>"""

    return HttpResponse(html)

def thumbnail(request):
    # print('request:', dir(request))
    # print('r', request.get_host())
    # print('r', request.get_port())

    logger.info('h:', request.get_host(), 'p:', request.get_port())

    uuid = request.GET.get('d')
    if not op.exists(hss.THUMBNAILS_ROOT):
        os.makedirs(hss.THUMBNAILS_ROOT)
    output_file = op.join(hss.THUMBNAILS_ROOT, uuid + ".png")

    if not op.exists(output_file):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            screenshot(
                '{}:{}/app/'.format(request.get_host(), request.get_port()),
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
    print('base_url:', base_url)
    page = await browser.newPage()
    await page.goto(f'{base_url}?config={uuid}', {
        'waitUntil': 'networkidle2',
    })
    await page.screenshot({'path': output_file})
    await browser.close()