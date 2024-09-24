import logging

from django_utils_lib.constants import PACKAGE_NAME

pkg_logger = logging.getLogger(PACKAGE_NAME)
pkg_logger.setLevel(logging.INFO)
