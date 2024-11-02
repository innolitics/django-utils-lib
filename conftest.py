from django.conf import global_settings, settings

pytest_plugins = ["pytester", "django_utils_lib.testing.pytest_plugin"]

# Set up dummy settings for any tests that rely on Django internals
# being able to bootstrap against settings.py
settings.configure(default_settings=global_settings)
settings.DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
settings.INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
