from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from SDIMS_apps.instructors.models import Instructor
from SDIMS_apps.trainees.models import Trainee
from SDIMS_apps.accounts.decorators import admin_required

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
                return redirect('accounts:admin_dashboard')
            elif user.role == 'instructor':
                return redirect('accounts:instructor_dashboard')
            else:
                return redirect('accounts:trainee_dashboard')

        return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def generate_password():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def generate_username(phone):
    return f"user_{phone[-4:]}"   # simple logic (improve later)

# ADMIN
@login_required
@admin_required
def admin_dashboard(request):
    if request.user.role != 'admin':
        return redirect('accounts:login')

    # Stats
    total_users = User.objects.count()
    total_instructors = Instructor.objects.count()
    total_trainees = Trainee.objects.count()
    active_trainees = Trainee.objects.filter(status__in=['ENROLLED', 'TRAINING']).count()

    # Recent users (last 5)
    recent_users = User.objects.order_by('-id')[:5]

    context = {
        'total_users': total_users,
        'total_instructors': total_instructors,
        'total_trainees': total_trainees,
        'active_trainees': active_trainees,
        'recent_users': recent_users,
    }

    return render(request, 'admin_dashboard.html', context)


# INSTRUCTOR 
@login_required
def instructor_dashboard(request):
    if not hasattr(request.user, 'instructor'):
        return redirect('index')

    instructor = request.user.instructor

    trainees = Trainee.objects.all()

    return render(request, 'instructor_dashboard.html', {
        'instructor': instructor,
        'trainees': trainees,
    })


# TRAINEE 
@login_required
def trainee_dashboard(request):
    if request.user.role != 'student':
        return redirect('accounts:login')

    trainee = request.user.trainee

    fee_record = getattr(trainee, 'fee_record', None)

    paid = fee_record.total_paid() if fee_record else 0
    remaining = fee_record.remaining() if fee_record else 0
    discount = fee_record.discount_amount if fee_record else 0
    final_fee = fee_record.final_fee() if fee_record else 0

    return render(request, 'trainee_dashboard.html', {
        'trainee': trainee,
        'fee_record': fee_record,
        'paid': paid,
        'remaining': remaining,
        'discount': discount,
        'final_fee': final_fee,
    })