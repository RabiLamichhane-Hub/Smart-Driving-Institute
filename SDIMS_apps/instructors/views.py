from django.shortcuts import render, get_object_or_404, redirect
from .models import Instructor
from .forms import InstructorForm
from SDIMS_apps.accounts.forms import CreateUserForm
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from SDIMS_apps.accounts.decorators import role_required
from SDIMS_apps.accounts.views import generate_password, generate_username


User = get_user_model()

# List all instructors

def instructor_list(request):

    # optimize query (joins user table)
    instructors = Instructor.objects.select_related('user').all()

    # stats (optional but useful)
    total_instructors = instructors.count()
    active_instructors = instructors.filter(status='active').count()

    context = {
        'instructors': instructors,
        'total_instructors': total_instructors,
        'active_instructors': active_instructors,
    }

    return render(request, 'instructor_list.html', context)

# Add new instructor
@login_required
@role_required(['admin'])
def instructor_create(request):
    # Only admin can create instructors
    if request.user.role != 'admin':
        return redirect('accounts:login')

    if request.method == "POST":
        user_form = CreateUserForm(request.POST)
        instructor_form = InstructorForm(request.POST)

        if user_form.is_valid() and instructor_form.is_valid():
            data = user_form.cleaned_data

            # Generate credentials
            username = generate_username(data['phone'])
            password = generate_password()

            # Create User
            user = User.objects.create_user(
                username=username,
                password=password,
                role='instructor',
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone=data['phone'],
                address=data['address'],
                email=data['email']
            )

            # Create Instructor
            instructor = instructor_form.save(commit=False)
            instructor.user = user
            instructor.save()

            return render(request, 'instructor_created.html', {
                'username': username,
                'password': password,
                'user': user,
                'instructor': instructor,
            })

    else:
        user_form = CreateUserForm()
        instructor_form = InstructorForm()

    return render(request, 'instructor_form.html', {
        'user_form': user_form,
        'instructor_form': instructor_form
    })

# Edit existing instructor
@login_required
@role_required(['admin'])
def instructor_update(request, pk):
    instructor = get_object_or_404(Instructor, pk=pk)
    user = instructor.user

    if request.method == 'POST':
        user_form = CreateUserForm(request.POST, instance=user)
        instructor_form = InstructorForm(request.POST, instance=instructor)

        if user_form.is_valid() and instructor_form.is_valid():
            user_form.save()
            instructor_form.save()
            return redirect('instructors:instructor_list')

    else:
        user_form = CreateUserForm(instance=user)
        instructor_form = InstructorForm(instance=instructor)

    return render(request, 'instructor_form.html', {
        'user_form': user_form,
        'instructor_form': instructor_form
    })

# Delete instructor
@login_required
@role_required(['admin'])
def instructor_delete(request, pk):
    instructor = get_object_or_404(Instructor, pk=pk)
    if request.method == 'POST':
        user = instructor.user
        user.delete() 
        return redirect('instructors:instructor_list')
    return render(request, 'instructor_confirm_delete.html', {'instructor': instructor})