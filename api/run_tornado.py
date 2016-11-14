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

try:
    server_port = sys.argv[1]
except IndexError as e:
    sys.stderr.write("Server port required as first argument\n")
    sys.exit(1)

define('port', type=int, default=server_port)


class HelloHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(u"yolo")


def main():
    os.environ['DJANGO_SETTINGS_MODULE'] = "api.settings"
    sys.path.append('api')  # path to your project if needed

    parse_command_line()

    wsgi_app = get_wsgi_application()
    container = tornado.wsgi.WSGIContainer(wsgi_app)
    public_root = os.path.join(os.path.dirname(__file__), 'static')
    settings = dict(
        static_path=public_root,
        template_path=public_root,
    )

    tornado_app = tornado.web.Application(
        [
            # (r'/static/', tornado.web.StaticFileHandler,
            # dict(path=settings['static_path'])),
            ('/hello-tornado', HelloHandler),
            ('.*', tornado.web.FallbackHandler, dict(fallback=container)),
            (r'/', tornado.web.StaticFileHandler, {'path': public_root}),
            # ('.*', tornado.web.FallbackHandler, dict(fallback=container)),
        ], **settings)

    server = tornado.httpserver.HTTPServer(tornado_app)
    server.listen(options.port, '0.0.0.0')

    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()
