from abc import ABC, abstractmethod
from typing import Callable, Final
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from django_utils_lib.logger import pkg_logger

GetResponseCallable = Callable[[HttpRequest], HttpResponse]


class BaseMiddleware(ABC):
    def __init__(self, get_response: GetResponseCallable):
        self.get_response = get_response

    @abstractmethod
    def __call__(self, request: HttpRequest) -> HttpResponse:
        return NotImplemented


class DANGEROUS_DisableCSRFMiddleware(BaseMiddleware):
    """
    USE WITH CAUTION: This middleware completely disables CSRF checks, and as
    such, should only be used in development
    """

    def __call__(self, request: HttpRequest) -> HttpResponse:
        setattr(request, "_dont_enforce_csrf_checks", True)
        response = self.get_response(request)
        return response


class DevServerRedirectMiddleware(BaseMiddleware):
    """
    FOR DEVELOPMENT USE ONLY: A middleware that intercepts redirects responses
    and modifies the host to match a requested dev server (sniffed via referer).

    Useful for instances in which your frontend dev server is running on a different
    host and/or port than Django (basically guaranteed to happen with any live
    reloading frontend dev server).

    For example, if using standard ports and Next.js, your frontend dev server
    might be :3000, but Django would be :8000. So this middleware would be helpful
    for automatically patching :8000 -> :3000, so you can stay on your frontend
    dev server after hitting the backend.

    Use `DEV_SERVER_ACCEPTED_DEV_SERVER_PORTS` to control, with List[Union[int, str]]
    """

    DJANGO_SETTINGS_KEY: Final = "DEV_SERVER_ACCEPTED_DEV_SERVER_PORTS"

    def __call__(self, request: HttpRequest) -> HttpResponse:
        settings_key = DevServerRedirectMiddleware.DJANGO_SETTINGS_KEY
        accepted_dev_ports_setting = getattr(settings, settings_key, [])
        if not isinstance(accepted_dev_ports_setting, list):
            raise ValueError(
                f"Invalid value for settings.{settings_key} - expected list, but got {type(accepted_dev_ports_setting)}"
            )

        # Safe-guard against accidental inclusion
        assert (
            "PROD" not in getattr(settings, "RUNTIME_ENV", "").upper()
        ), "You should not use the dev server redirect middleware in a production environment"

        referer = request.headers.get("referer", "")
        response = self.get_response(request)

        if not (300 <= response.status_code < 400):
            return response

        for port in accepted_dev_ports_setting:
            if not isinstance(port, (str, int)):
                pkg_logger.warning(f"Invalid port value: {port}")
                continue
            if f":{port}" in referer:
                referrer_url = urlparse(referer)
                original_redirect_url = urlparse(response["Location"])

                # Swap out just the protocol://hostname:port section
                redirect_url = original_redirect_url._replace(scheme=referrer_url.scheme, netloc=referrer_url.netloc)

                pkg_logger.info(
                    f"DevServerRedirectMiddleware: Modified redirect from {original_redirect_url.geturl()} to "
                    f"{redirect_url.geturl()}"
                )

                response["Location"] = redirect_url.geturl()

        return response
