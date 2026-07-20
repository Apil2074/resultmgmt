"""
core/signals.py
---------------
Shared Django signal receivers for automatic old-file cleanup on ImageField updates.

Usage — in any model file:

    from core.signals import delete_old_image_on_change, delete_image_on_delete

    # Replace old image when a new one is uploaded
    @receiver(pre_save, sender=MyModel)
    def my_model_image_cleanup(sender, instance, **kwargs):
        delete_old_image_on_change(instance, 'photo')   # field name as string

    # Delete image file when the model record is deleted
    @receiver(post_delete, sender=MyModel)
    def my_model_image_delete(sender, instance, **kwargs):
        delete_image_on_delete(instance, 'photo')
"""

import os
import logging
from django.db.models.signals import pre_save, post_delete

logger = logging.getLogger(__name__)


def _delete_file_safe(path: str) -> None:
    """Delete a file from the filesystem, silently ignoring missing files."""
    if path and os.path.isfile(path):
        try:
            os.remove(path)
            logger.debug("Deleted old media file: %s", path)
        except OSError as e:
            # Log but don't crash — a missing/locked file is not fatal
            logger.warning("Could not delete old media file %s: %s", path, e)


def delete_old_image_on_change(instance, field_name: str) -> None:
    """
    Called from a pre_save signal. Compares the current database value of
    `field_name` against the new value on `instance`. If they differ (i.e.
    a new image has been uploaded), the old file is deleted from storage.

    Also deletes the old file if the field is explicitly cleared (set to None
    or empty string), so stale files never accumulate.
    """
    if not instance.pk:
        # New record — no old file to worry about
        return

    Model = instance.__class__
    try:
        old_instance = Model.objects.get(pk=instance.pk)
    except Model.DoesNotExist:
        return

    old_field = getattr(old_instance, field_name)
    new_field = getattr(instance, field_name)

    old_name = old_field.name if old_field else None
    new_name = new_field.name if new_field else None

    if old_name and old_name != new_name:
        # The field has changed — delete the old physical file
        _delete_file_safe(old_field.path)


def delete_image_on_delete(instance, field_name: str) -> None:
    """
    Called from a post_delete signal. Deletes the image file from storage
    when a model record is fully deleted from the database.
    """
    field = getattr(instance, field_name)
    if field and field.name:
        try:
            _delete_file_safe(field.path)
        except ValueError:
            # field.path raises ValueError if the field has no file
            pass
