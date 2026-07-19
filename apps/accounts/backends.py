"""
Custom authentication backend that allows users to log in
using either their username OR their registered email address.
"""
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import User


class EmailOrUsernameBackend(ModelBackend):
    """
    Authenticate against username or email.
    Accepts the same `username` field from the login form and checks it
    against both the username and email columns.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        try:
            # Look for a user whose username OR email matches (case-insensitive)
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except User.DoesNotExist:
            # Run the default password hasher once to reduce timing attacks
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # If somehow two accounts share an email, fall back to exact username match
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
