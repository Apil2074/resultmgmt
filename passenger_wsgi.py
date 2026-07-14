import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(__file__))

def application(environ, start_response):
    try:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.production'
        if 'DJANGO_SETTINGS_MODULE' in environ:
            environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.production'
            
        from django.core.wsgi import get_wsgi_application
        _application = get_wsgi_application()
        return _application(environ, start_response)
    except Exception as e:
        status = '500 Internal Server Error'
        output = b"Django Startup Error:\n\n"
        output += traceback.format_exc().encode('utf-8')
        response_headers = [('Content-type', 'text/plain'), ('Content-Length', str(len(output)))]
        start_response(status, response_headers)
        return [output]
