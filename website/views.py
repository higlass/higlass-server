import subprocess
import pyppeteer
import asyncio
import os
import os.path as op
from pyppeteer import launch
import tempfile

import higlass_server.settings as hss

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
    uuid = request.GET.get('d')
    if not op.exists(hss.THUMBNAILS_ROOT):
        os.makedirs(hss.THUMBNAILS_ROOT)
    output_file = op.join(hss.THUMBNAILS_ROOT, uuid + ".png")

    if not op.exists(output_file):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            screenshot(
                hss.THUMBNAIL_RENDER_URL_BASE,
                uuid,
                output_file))
        loop.close()

    with open(output_file, 'rb') as f:
        return HttpResponse(
            f.read(),
            content_type="image/jpeg")

async def screenshot(base_url, uuid, output_file):
    browser = await launch(
        headless=true,
        args=['--no-sandbox'],
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False
    )
    page = await browser.newPage()
    await page.goto(f'{base_url}?config={uuid}', {
        'waitUntil': 'networkidle2',
    })
    await page.screenshot({'path': output_file})
    await browser.close()
