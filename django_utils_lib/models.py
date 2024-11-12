import uuid

from django.db import models


class BaseModelWithIdAndTimestamps(models.Model):
    """
    This is a useful "base model" to have all your other models inherit from

    It provides:

    - A UUID(4) backed "id" property, as the primary key
    - Timestamps (`created_date`, `modified_date`)
    - Enforcement of validation rules on save (which is not Django's default behavior)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, editable=False)  # noqa: A003

    # Timestamps
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    # Run all validation checks on model save (which is not the default behavior of Django)
    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        abstract = True
