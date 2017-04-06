import logging

from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)


class CoolerFileBroken(APIException):
    status_code = 500
    default_detail = 'The cooler file is broken.'
    default_code = 'cooler_file_broken'
