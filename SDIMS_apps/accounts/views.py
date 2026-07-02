from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
import string
import secrets

User = get_user_model()


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
 
        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, "login.html", {"username": username})
 
        user = authenticate(request, username=username, password=password)
 
        if user is not None:
            # Superusers default to admin role
            if user.is_superuser and not user.role:
                user.role = 'admin'
                user.save(update_fields=['role'])

            login(request, user)
            if user.role == "admin" or user.is_superuser:
                return redirect("homesandall:admin_dashboard")
            elif user.role == "supervisor":
                return redirect("homesandall:supervisor_dashboard")
            elif user.role == "instructor":
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


@login_required
def change_password_view(request):
    """
    Handles first-time and voluntary password changes.
    On success, clears must_change_password and updates the session
    so the user is not logged out.
    """
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        # Clear the forced-change flag
        user.must_change_password = False
        user.save(update_fields=['must_change_password'])
        # Keep the user logged in after the password change
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed successfully.")
        from SDIMS_apps.accounts.decorators import get_dashboard_url
        return redirect(get_dashboard_url(request.user))

    return render(request, 'change_password.html', {'form': form})


def generate_password(length=10):
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_username(phone):
    base = f"user_{phone[-4:]}"
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}_{counter}"
        counter += 1
    return username