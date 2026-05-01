from django.shortcuts import render, redirect

def get_dashboard_url(user):
    if user.role == 'admin':
        return 'homesandall:admin_dashboard'
    elif user.role == 'instructor':
        return 'homesandall:instructor_dashboard'
    elif user.role == 'supervisor':
        return 'homesandall:instructor_dashboard'
    elif user.role == 'trainee':
        return 'homesandall:trainee_dashboard'
    return 'login'


def role_required(allowed_roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):

            # Not logged in → login page
            if not request.user.is_authenticated:
                return redirect('login')

            # Logged in but wrong role → access denied page
            if request.user.role not in allowed_roles:
                return render(request, 'access_denied.html', {
                    'dashboard_url': get_dashboard_url(request.user)
                })

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator