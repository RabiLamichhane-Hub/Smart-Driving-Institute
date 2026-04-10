from django.shortcuts import redirect

def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'admin':
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_or_instructor_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.role not in ['admin', 'instructor']:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper