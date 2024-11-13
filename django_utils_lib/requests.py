import json
import os
import re
import tempfile
from typing import Dict, Final, List, Literal, Optional, TypedDict, Union

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
from typing_extensions import NotRequired

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
    json_context_key: str = pydantic.Field(default="__DJANGO_CONTEXT__")
    """
    If injecting JSON context into the HTML response of a request, this key will be
    used to store the data, under the window global (e.g. accessible via
    `window.{json_context_key}` or `globalThis.{json_context_key}`).

    Default = `__DJANGO_CONTEXT__`
    """
    json_context_injection_location: Literal["head", "body"] = pydantic.Field(default="head")
    """
    If injecting JSON context into the HTML response of a request, this is where
    (the HTML tag) in which it will be injected as a nested script tag.

    Default = `"head"`
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

    class JSONContext(TypedDict):
        data: Dict
        """
        The data to inject into a request, via JSON embedded in a script tag
        """
        global_key: NotRequired[Optional[str]]
        """
        The global key under which to store the data / make accessible via JS

        Defaults to the `config.json_context_key` value, which itself defaults to
        `__DJANGO_CONTEXT__`
        """
        injection_location: NotRequired[Optional[str]]
        """
        Where to inject the script tag containing the JSON payload

        Defaults to the `config.json_context_injection_location` value, which itself
        defaults to `"head"`
        """

    def serve_static_path(
        self,
        request: HttpRequest,
        asset_path: str,
        url_path: Optional[str] = None,
        json_data: Optional[JSONContext] = None,
    ) -> Union[HttpResponse, FileResponse]:
        """
        This should be close to a drop-in replacement for `serve` (it wraps it),
        with config-based logic for how to handle the request

        > **Note**: The difference between `asset_path` and `url_path` is that `asset_path`
        is the actual filesystem path (relative to staticfiles root) and `url_path`
        is what the user sees as the path. They _can_ be different, but don't _have_
        to be. A good use-case for having them different values is so that you can use
        something like `/my_page/` as the `url_path`, but `/my_page/index.html` as the
        `asset_path`.

        Additionally, it supports dynamically injecting context into an HTML response,
        by injecting the context as a JSON payload inside an injected script tag.

        > **Warning**: This dynamic script injection has performance implications and could
        probably be optimized a bit.
        """
        if request.method not in ["GET", "HEAD", "OPTIONS"]:
            return HttpResponseNotAllowed(["GET", "HEAD", "OPTIONS"])
        url_path = url_path or request.path
        if (response := self.guard_path(request, url_path)) is not None:
            return response
        if json_data is None:
            return serve(request, document_root=str(settings.STATIC_ROOT), path=asset_path)

        if not asset_path.endswith(".html"):
            raise ValueError("Cannot inject JSON context into a non-HTML asset")

        # To render json data context into the page, we will inject is a script tag, with ...
        global_json_key = json_data.get("global_key", self.config.json_context_key)
        assert global_json_key is not None
        injectable_json_script_tag_str = f"<script>window.{global_json_key} = {json.dumps(json_data['data'])};</script>"

        injection_location = json_data.get("injection_location", self.config.json_context_injection_location)
        assert injection_location in ["head", "body"]

        raw_html_path = os.path.join(settings.STATIC_ROOT or "", asset_path.lstrip("/"))
        raw_html_code = open(raw_html_path, "r").read()
        if injection_location == "head":
            final_html_code = raw_html_code.replace("<head>", f"<head>{injectable_json_script_tag_str}")
        else:
            final_html_code = raw_html_code.replace("</body>", f"{injectable_json_script_tag_str}</body>")
            # safe_join
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as temp_file:
            temp_file.write(final_html_code)
            temp_file_path = temp_file.name
            print(temp_file_path)
            return serve(request, document_root="/", path=temp_file_path.lstrip("/"))

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
                r"^(?P<asset_path>[^?#]+).*$",
                lambda request, asset_path: self.serve_static_path(
                    request, f"{asset_path.removesuffix('/')}/index.html"
                ),
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
