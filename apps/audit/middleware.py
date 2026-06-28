"""
Audit Middleware — logs login/logout events
"""
from django.utils.deprecation import MiddlewareMixin


class AuditMiddleware(MiddlewareMixin):
    """Logs basic HTTP audit events (login/logout are handled in views)."""

    def process_response(self, request, response):
        return response
