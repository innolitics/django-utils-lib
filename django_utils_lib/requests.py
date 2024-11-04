import re
from typing import Dict, Final, List, Optional, Union

import pydantic
from django.conf import settings
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)
from django.urls import re_path
from django.views.static import serve

from django_utils_lib.lazy import lazy_django


class SimpleStaticFileServerConfig(pydantic.BaseModel):
    auth_required_path_patterns: Optional[List[re.Pattern]] = pydantic.Field(default=None)
    """
    A list of URL path patterns that, if matched, should require that the request
    be from an authenticated user
    """
    forbidden_path_patterns: Optional[List[re.Pattern]] = pydantic.Field(default=None)
    """
    A list of URL path patterns that, if matched, should result in a Forbidden response
    """
    block_bare_html_access: bool = pydantic.Field(default=True)
    """
    Whether or not paths that point directly to HTML files should be blocked.

    For example, a settings of `True` would block `/dir/index.html`, but `/dir/`
    would be permissible (unless blocked by a different access rule)
    """


class SimpleStaticFileServer:
    """
    This is a class to help with serving static files directly with
    Django.

    For a more robust solution, one should look to using a CDN and/or
    standalone static file server with a reverse-proxy in place.
    """

    DJANGO_SETTINGS_KEY: Final = "SIMPLE_STATIC_FILE_SERVER_CONFIG"

    def __init__(self, config: Optional[SimpleStaticFileServerConfig]) -> None:
        if not config:
            config = getattr(settings, SimpleStaticFileServer.DJANGO_SETTINGS_KEY, None)
        try:
            validated_config = SimpleStaticFileServerConfig.model_validate(config)
            self.config = validated_config
        except pydantic.ValidationError as err:
            if config is None:
                # Use default config
                self.config = SimpleStaticFileServerConfig()
            else:
                raise ValueError(f"Invalid config for SimpleStaticFileServer: {err}")

    def guard_path(self, request: HttpRequest, url_path: str) -> Optional[HttpResponse]:
        """
        Checks if a given URL path should have its normal resolution interrupted,
        based on the configuration

        Returns `None` if the processing chain should be continued as-is, or returns
        a `HttpResponse` if the chain should end and the response immediately sent back
        """
        # Check for bare access first, since this should be the fastest check
        if self.config.block_bare_html_access and url_path.endswith(".html"):
            return HttpResponseNotFound()
        # Check explicit block list
        if any(pattern.search(url_path) for pattern in self.config.forbidden_path_patterns or []):
            return HttpResponseForbidden()
        # Check for attempted access to an auth-required path from a non-authed user
        if self.config.auth_required_path_patterns and not request.user.is_authenticated:
            if any(pattern.search(url_path) for pattern in self.config.auth_required_path_patterns):
                return lazy_django.redirect_to_login(next=request.get_full_path())

        # Pass request forward / noop
        return None

    def serve_static_path(
        self, request: HttpRequest, asset_path: Optional[str] = None
    ) -> Union[HttpResponse, FileResponse]:
        """
        This should be close to a drop-in replacement for `serve` (it wraps it),
        with config-based logic for how to handle the request
        """
        if request.method not in ["GET", "HEAD", "OPTIONS"]:
            return HttpResponseNotAllowed(["GET", "HEAD", "OPTIONS"])
        url_path = asset_path or request.path
        if (response := self.guard_path(request, url_path)) is not None:
            return response
        return serve(request, document_root=str(settings.STATIC_ROOT), path=url_path)

    def generate_url_patterns(self, ignore_start_strings: Optional[List[str]] = None):
        """
        Generates some pattern matchers you can stick in `urlpatterns` (albeit greedy). Should go last.
        """
        ignore_start_strings = ignore_start_strings or ["/static/", "/media/"]
        negate_start_pattern = "".join([f"(?!{s})" for s in ignore_start_strings])
        return [
            # Capture paths with extensions, and pass through as-is
            re_path(rf"^{negate_start_pattern}(?P<asset_path>.*\..*)$", self.serve_static_path),
            # For extension-less paths, try to map to an `index.html`
            re_path(
                r"^(?P<asset_path>.+/$)",
                lambda request, asset_path: self.serve_static_path(request, f"{asset_path}/index.html"),
            ),
        ]


def object_to_multipart_dict(obj: Dict, existing_multipart_dict: Optional[dict] = None, key_prefix="") -> Dict:
    """
    This is basically the inverse of a multi-part form parser, which can additionally
    handle nested entries.

    The main use-case for this is constructing requests in Python that emulate
    a multipart FormData payload that would normally be sent by the frontend.

    Nested entries get flattened / hoisted, so that the final dict is a flat
    key-value map, with bracket notation used for nested entries. List items are
    also hoisted up, with indices put within leading brackets.

    Warning: values are not stringified (but would be in a true multipart payload)

    @example
    ```
    nested_dict = {"a": 1, "multi": [{"id": "abc"}, {"id": "123"}]}
    print(object_to_multipart_dict(nested_dict))
    # > {'a': 1, 'multi[0][id]': 'abc', 'multi[1][id]': '123'}
    ```
    """
    result = existing_multipart_dict or {}
    for _key, val in obj.items():
        # If this is a nested child, we need to wrap key in brackets
        _key = f"[{_key}]" if existing_multipart_dict else _key
        key = key_prefix + _key
        if isinstance(val, dict):
            object_to_multipart_dict(val, result, key)
        elif isinstance(val, (list, tuple)):
            for i, sub_val in enumerate(val):
                sub_key = f"{key}[{i}]"
                if isinstance(sub_val, dict):
                    object_to_multipart_dict(sub_val, result, sub_key)
                else:
                    result[sub_key] = sub_val
        else:
            result[key] = val
    return result
