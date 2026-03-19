from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

class CustomLoginView(LoginView):
    template_name = 'login.html'

    def get_success_url(self):
        return reverse_lazy('accounts:redirect_user')   # 👈 THIS LINE

def redirect_user(request):
    if request.user.role == 'admin':
        return redirect('accounts:admin_dashboard')
    elif request.user.role == 'instructor':
        return redirect('accounts:instructor_dashboard')
    else:
        return redirect('accounts:trainee_dashboard')

def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')

def instructor_dashboard(request):
    return render(request, 'instructor_dashboard.html')

def trainee_dashboard(request):
    return render(request, 'trainee_dashboard.html')