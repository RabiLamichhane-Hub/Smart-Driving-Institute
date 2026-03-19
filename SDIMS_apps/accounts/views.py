from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

class CustomLoginView(LoginView):
    template_name = 'login.html'

    def get_success_url(self):
        return reverse_lazy('accounts:redirect_user')   # 👈 THIS LINE

def redirect_user(request):
    if request.user.role == 'admin':
        return redirect('admin_dashboard')
    elif request.user.role == 'instructor':
        return redirect('instructor_dashboard')
    else:
        return redirect('student_dashboard')