import subprocess
import pyppeteer
import asyncio
import os.path as op
from pyppeteer import launch
import tempfile

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

def preview(request):
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_file = op.join(tmp_dir, 'screenshot.png')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(screenshot(output_file))
        loop.close()


        with open(output_file, 'rb') as f:
            return HttpResponse(
                f.read(),
                content_type="image/jpeg")

async def screenshot(output_file):
    browser = await launch(
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False
    )
    print("hi")
    page = await browser.newPage()
    await page.goto('http://higlass.io/app/?config=MSHhOBbOSW6iIovB5yk6BA', {
        'waitUntil': 'networkidle2',
    })
    await page.screenshot({'path': output_file})
    await browser.close()