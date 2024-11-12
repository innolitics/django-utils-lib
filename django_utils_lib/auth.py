from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.password_validation import validate_password
from typing_extensions import NotRequired, TypedDict


class BaseUserCreationArgs(TypedDict):
    """
    A starting point for strongly-typing the creation parameters associated with creating
    a new user.
    """

    is_staff: NotRequired[bool]
    is_active: NotRequired[bool]
    is_superuser: NotRequired[bool]


class EmailBasedUserManager(BaseUserManager):
    """
    It is commonly useful to change the default Django User model to use emails instead of usernames

    This is a custom user manager that helps to facilitate this.

    NOTE: This manager assumes that you have registered your custom User (for use with this manager,
    and as as the User "creator") in `settings.py`, with `AUTH_USER_MODEL = "your.model.path"`
    """

    use_in_migrations = True

    def _create_user(self, email: str, password: str, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        validate_password(password)
        user = get_user_model().objects.create(email=email, password=password, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_user(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)
