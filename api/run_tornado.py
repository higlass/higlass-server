#!/usr/bin/env python
#
# Runs a Tornado web server with a django project
# Make sure to edit the DJANGO_SETTINGS_MODULE to point to your settings.py
#
# http://localhost:8080/hello-tornado
# http://localhost:8080

import sys
import os

from tornado.options import options, define, parse_command_line
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.wsgi

from django.core.wsgi import get_wsgi_application


define('port', type=int, default=8000)


class HelloHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('Hello from tornado')


def main():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'api.settings' # TODO: edit this
    sys.path.append('/home/ubuntu/api') # path to your project if needed

    parse_command_line()

    wsgi_app = get_wsgi_application()
    container = tornado.wsgi.WSGIContainer(wsgi_app)

    tornado_app = tornado.web.Application(
        [
            (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': '../web/'}),
	    ('/hello-tornado', HelloHandler),
            ('.*', tornado.web.FallbackHandler, dict(fallback=container)),
        ])

    server = tornado.httpserver.HTTPServer(tornado_app)
    server.listen(options.port,'0.0.0.0')

    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
