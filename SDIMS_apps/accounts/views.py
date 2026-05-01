from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model

from .forms import CreateUserForm
import random
import string

User = get_user_model()

def register_view(request):
    if request.method == "POST":
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])  # HASH PASSWORD
            user.save()
            login(request, user)
            return redirect('accounts:dashboard')  # adjust later
    else:
        form = CreateUserForm()

    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            # role-based redirect
            if user.role == 'admin':
                return redirect('homesandall:admin_dashboard')
            elif user.role == 'instructor':
                return redirect('homesandall:instructor_dashboard')
            else:
                return redirect('homesandall:trainee_dashboard')

        return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def generate_password():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def generate_username(phone):
    return f"user_{phone[-4:]}"   # simple logic (improve later)

