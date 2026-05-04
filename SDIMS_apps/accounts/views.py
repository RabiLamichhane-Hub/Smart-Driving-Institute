from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib import messages

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
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
 
        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, "login.html", {"username": username})
 
        user = authenticate(request, username=username, password=password)
 
        if user is not None:
            login(request, user)
            if user.role == "admin":
                return redirect("homesandall:admin_dashboard")
            elif user.role == "instructor" or user.role == "supervisor":
                return redirect("homesandall:instructor_dashboard")
            elif user.role == "trainee":
                return redirect("homesandall:trainee_dashboard")
            else:
                return redirect("accounts:login")
 
        messages.error(request, "Invalid username or password. Please try again.")
        return render(request, "login.html", {"username": username})
 
    return render(request, "login.html")

def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def generate_password():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def generate_username(phone):
    return f"user_{phone[-4:]}"   # simple logic (improve later)

