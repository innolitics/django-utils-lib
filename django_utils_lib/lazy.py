from typing import Callable, Optional


class LazyDjango:
    """
    Django has a few modules where if you import something from them,
    they trigger side-effects that can crash the app if called at import-time
    vs run-time. Notably things related to auth that trigger apps / settings
    checks.

    This class is a workaround, without using a full app registration system,
    to just use lazy-imports.
    """

    _redirect_to_login: Optional[Callable] = None

    @property
    def redirect_to_login(self):
        if self._redirect_to_login is None:
            from django.contrib.auth.views import redirect_to_login

            self._redirect_to_login = redirect_to_login
        return self._redirect_to_login


lazy_django = LazyDjango()
