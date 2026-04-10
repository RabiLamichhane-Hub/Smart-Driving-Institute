from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from SDIMS_apps.accounts.forms import CreateUserForm
from SDIMS_apps.accounts.views import generate_username, generate_password
from .forms import TraineeForm
from SDIMS_apps.accounts.decorators import admin_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from . models import Trainee

User = get_user_model()

# Create your views here.
def register(request):
    if request.method == 'POST':
        user_form = CreateUserForm(request.POST)
        trainee_form = TraineeForm(request.POST)

        if user_form.is_valid() and trainee_form.is_valid():
            # Create user but don't save yet
            user = user_form.save(commit=False)
            user.role = 'student'

            # Generate credentials from cleaned data
            username = generate_username(user_form.cleaned_data['phone'])
            password = generate_password()

            user.username = username
            user.set_password(password)
            user.save()

            # Create trainee and link to user
            trainee = trainee_form.save(commit=False)
            trainee.user = user
            trainee.save()

            return render(request, 'user_created.html', {
                'username': username,
                'password': password,
                'trainee': trainee,
            })

        # If forms invalid, fall through and re-render with errors

    else:
        user_form = CreateUserForm()
        trainee_form = TraineeForm()

    return render(request, 'register.html', {
        'user_form': user_form,
        'trainee_form': trainee_form,
    })


def trainee_list(request):
    trainees = Trainee.objects.all()

    context = {
        'trainees': trainees
    }
    return render(request, 'trainee_list.html', context)

@login_required
@admin_required
def trainee_edit(request, pk):
    trainee = get_object_or_404(Trainee, pk=pk)
    if request.method == 'POST':
        trainee_form = TraineeForm(request.POST, instance=trainee)
        if trainee_form.is_valid():
            trainee_form.save()
            messages.success(request, "Trainee updated successfully.")
            return redirect('trainees:trainee_list')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        trainee_form = TraineeForm(instance=trainee)

    return render(request, 'trainee_edit.html', {
        'trainee_form': trainee_form,
        'trainee': trainee,
    })

@login_required
@admin_required
def trainee_delete(request, pk):
    trainee = get_object_or_404(Trainee, pk=pk)
    if request.method == 'POST':
        trainee.user.delete()  # deletes user and trainee together via CASCADE
        messages.success(request, "Trainee deleted successfully.")
        return redirect('trainees:trainee_list')

    return render(request, 'trainee_confirm_delete.html', {
        'trainee': trainee,
    })