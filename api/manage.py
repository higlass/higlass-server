#!/usr/bin/env python

import sys
from django.conf import settings

if __name__ == "__main__":
    # Setting DJANGO_SETTINGS_MODULE directly can cause issues when deployed
    # alongside other Django applications. We combat this by using
    # `settings.configure()`
    # Example from Django Docs: http://bit.ly/2eXMITo
    settings.configure("api.settings", DEBUG=True)
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise
    execute_from_command_line(sys.argv)
