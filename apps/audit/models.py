"""
Audit App — AuditLog model
"""
from django.db import models


class AuditLog(models.Model):
    """Audit trail for all important user actions."""

    class Action(models.TextChoices):
        CREATE = 'CREATE', 'Created'
        UPDATE = 'UPDATE', 'Updated'
        DELETE = 'DELETE', 'Deleted'
        LOGIN = 'LOGIN', 'Logged In'
        LOGOUT = 'LOGOUT', 'Logged Out'
        PUBLISH = 'PUBLISH', 'Published'
        UNLOCK = 'UNLOCK', 'Unlocked'
        IMPORT = 'IMPORT', 'Imported'
        EXPORT = 'EXPORT', 'Exported'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='audit_logs', null=True, blank=True
    )
    user = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=300, blank=True)
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']

    def __str__(self):
        return (
            f"{self.user} {self.get_action_display()} "
            f"{self.model_name} #{self.object_id} at {self.timestamp}"
        )
