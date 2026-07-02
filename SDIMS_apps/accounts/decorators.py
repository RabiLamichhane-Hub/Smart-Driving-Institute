import functools
from django.shortcuts import render, redirect

def get_dashboard_url(user):
    if user.is_superuser or user.role == 'admin':
        return 'homesandall:admin_dashboard'
    elif user.role == 'instructor':
        return 'homesandall:instructor_dashboard'
    elif user.role == 'supervisor':
        return 'homesandall:supervisor_dashboard'
    elif user.role == 'trainee':
        return 'homesandall:trainee_dashboard'
    return 'accounts:login'


def role_required(allowed_roles):
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):

            # Not logged in → login page
            if not request.user.is_authenticated:
                return redirect('accounts:login')

            # Superusers bypass role checks (they are always treated as admin)
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Logged in but wrong role → access denied page
            if request.user.role not in allowed_roles:
                return render(request, 'access_denied.html', {
                    'dashboard_url': get_dashboard_url(request.user)
                })

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator