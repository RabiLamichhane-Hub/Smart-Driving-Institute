"""
accounts/middleware.py

Enforces the must_change_password flag on the User model.
If a logged-in user has must_change_password=True, they are
redirected to the change-password page on every request
(except for the change-password page itself, logout, and static files).
"""

from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """
    Redirects users with must_change_password=True to the
    change-password page after every login.
    """

    EXEMPT_URLS = [
        '/accounts/change-password/',
        '/accounts/logout/',
        '/admin/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and getattr(request.user, 'must_change_password', False)
            and not any(request.path.startswith(url) for url in self.EXEMPT_URLS)
        ):
            change_url = reverse('accounts:change_password')
            if request.path != change_url:
                return redirect(change_url)

        return self.get_response(request)
