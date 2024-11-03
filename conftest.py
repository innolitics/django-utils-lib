import pytest
from django.conf import global_settings, settings
from django.test.utils import setup_test_environment

pytest_plugins = ["pytester", "django_utils_lib.testing.pytest_plugin"]


def configure_django_settings():
    if settings.configured:
        return
    settings.configure(
        default_settings=global_settings,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
    )


def pytest_configure():
    # TODO: This is rather hacky and it would be great to find a cleaner way to
    # do this. However, the pytest-django fixture we are disabling here is hard
    # to alter in any other way, especially as it uses session-level autouse
    pytest.MonkeyPatch().setattr("pytest_django.plugin.django_test_environment", lambda: None)
    configure_django_settings()
    setup_test_environment(debug=False)
