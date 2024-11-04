import re
from typing import List, Optional, Type, TypedDict, Union, cast
from unittest import mock

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import FileResponse, HttpResponse, HttpResponseForbidden, HttpResponseNotFound, HttpResponseRedirect
from django.test import RequestFactory

from django_utils_lib.requests import SimpleStaticFileServer, SimpleStaticFileServerConfig


class StaticFileServerTestCase(TypedDict):
    config: Optional[SimpleStaticFileServerConfig]
    request_paths: List[str]
    expected_responses: List[Union[Type[HttpResponse], Type[FileResponse]]]


@pytest.mark.parametrize(
    "scenario",
    [
        # No custom config used - class should use defaults
        StaticFileServerTestCase(
            config=None,
            request_paths=["/index.html", "/music/song.html", "/app/"],
            expected_responses=[
                # Default config should block bare HTML
                HttpResponseNotFound,
                HttpResponseNotFound,
                # No default auth blocks
                FileResponse,
            ],
        ),
        StaticFileServerTestCase(
            config=SimpleStaticFileServerConfig(
                block_bare_html_access=False,
                forbidden_path_patterns=[re.compile(r"/dogs/.*"), re.compile(r"^/dogs/.*")],
            ),
            request_paths=["/dir/index.html", "/index.html", "/dir/adoption/dogs/fido.html"],
            expected_responses=[FileResponse, FileResponse, HttpResponseForbidden],
        ),
        StaticFileServerTestCase(
            {
                "config": SimpleStaticFileServerConfig(
                    block_bare_html_access=True,
                    forbidden_path_patterns=[re.compile(r"sourcemap.js")],
                    auth_required_path_patterns=[re.compile(r"^/app/")],
                ),
                "request_paths": ["/dir/index.html", "/index.html", "/hello/", "/app/"],
                "expected_responses": [HttpResponseNotFound, HttpResponseNotFound, FileResponse, HttpResponseRedirect],
            }
        ),
    ],
)
@mock.patch(
    "django_utils_lib.lazy.LazyDjango.redirect_to_login",
    new_callable=mock.PropertyMock(return_value=mock.MagicMock(return_value=HttpResponseRedirect(""))),
)
@mock.patch("django_utils_lib.requests.serve", return_value=FileResponse())
def test_path_guarding(
    mock_serve: mock.Mock,
    mock_redirect_to_login: mock.Mock,
    rf: RequestFactory,
    scenario: StaticFileServerTestCase,
):
    assert len(scenario["expected_responses"]) == len(scenario["request_paths"])
    server = SimpleStaticFileServer(config=scenario["config"])

    def check_response(
        response: Union[FileResponse, HttpResponse], expected_response: Union[Type[FileResponse], Type[HttpResponse]]
    ):
        assert isinstance(response, expected_response), url_path

        # Check that the final action taken by the middleware was correct,
        # and the right functions were called
        assert mock_serve.called is (True if issubclass(expected_response, FileResponse) else False), url_path
        if issubclass(expected_response, HttpResponseRedirect):
            assert mock_redirect_to_login.called is True
            # Check `next` param was used correctly
            assert mock_redirect_to_login.call_args.kwargs.get("next") == url_path

        else:
            assert mock_redirect_to_login.called is False
        assert mock_redirect_to_login.called is (True if issubclass(expected_response, HttpResponseRedirect) else False)

        mock_serve.reset_mock()

    for url_path, expected_response in zip(scenario["request_paths"], scenario["expected_responses"]):
        mock_request = rf.get(url_path)
        mock_request.user = AnonymousUser()

        check_response(server.serve_static_path(request=mock_request, asset_path=url_path), expected_response)

        # Based on request alone
        check_response(server.serve_static_path(request=mock_request), expected_response)


@pytest.mark.parametrize(
    "ignore_start_strings, expected_patterns",
    [
        (
            None,
            [
                re.compile(r"^(?!/static/)(?!/media/)(?P<asset_path>.*\..*)$"),
                re.compile(r"^(?P<asset_path>.+/$)"),
            ],
        ),
        (
            ["/assets/", "/files/"],
            [
                re.compile(r"^(?!/assets/)(?!/files/)(?P<asset_path>.*\..*)$"),
                re.compile(r"^(?P<asset_path>.+/$)"),
            ],
        ),
    ],
)
def test_generate_url_patterns(ignore_start_strings, expected_patterns):
    server = SimpleStaticFileServer(config=None)
    patterns = server.generate_url_patterns(ignore_start_strings=ignore_start_strings)

    assert len(patterns) == len(expected_patterns)
    for url_pattern, expected_pattern in zip(patterns, expected_patterns):
        re_pattern = cast(re.Pattern, url_pattern.pattern.regex)
        assert re_pattern.pattern == expected_pattern.pattern
