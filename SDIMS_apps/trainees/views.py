from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from SDIMS_apps.accounts.forms import CreateUserForm
from SDIMS_apps.accounts.views import generate_username, generate_password
from .forms import TraineeForm
from SDIMS_apps.accounts.decorators import role_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Trainee
from SDIMS_apps.courses.models import Course

User = get_user_model()


def register(request):
    if request.method == 'POST':
        user_form = CreateUserForm(request.POST)
        trainee_form = TraineeForm(request.POST)

        if user_form.is_valid() and trainee_form.is_valid():
            user = user_form.save(commit=False)
            user.role = 'trainee'

            username = generate_username(user_form.cleaned_data['phone'])
            password = generate_password()

            user.username = username
            user.set_password(password)
            user.save()

            trainee = trainee_form.save(commit=False)
            trainee.user = user
            trainee.save()

            return render(request, 'trainee_created.html', {
                'username': username,
                'password': password,
                'trainee': trainee,
            })

    else:
        user_form = CreateUserForm()
        trainee_form = TraineeForm()

    return render(request, 'register.html', {
        'user_form': user_form,
        'trainee_form': trainee_form,
    })


def trainee_list(request):
    trainees = Trainee.objects.all()
    return render(request, 'trainee_list.html', {'trainees': trainees})


@login_required
@role_required(['admin'])
def trainee_edit(request, pk):
    trainee = get_object_or_404(Trainee, pk=pk)

    if request.method == 'POST':
        trainee_form = TraineeForm(request.POST, instance=trainee)

        if trainee_form.is_valid():
            trainee_form.save()
            messages.success(request, "Trainee updated successfully.")
            return redirect('trainees:trainee_list')
    else:
        trainee_form = TraineeForm(instance=trainee)

    course_fee = trainee.course.fee if trainee.course else 0

    return render(request, 'trainee_edit.html', {
        'trainee_form': trainee_form,
        'trainee': trainee,
        'course_fee': course_fee,
    })


@login_required
@role_required(['admin'])
def trainee_delete(request, pk):
    trainee = get_object_or_404(Trainee, pk=pk)
    if request.method == 'POST':
        trainee.user.delete()
        messages.success(request, "Trainee deleted successfully.")
        return redirect('trainees:trainee_list')

    return render(request, 'trainee_confirm_delete.html', {'trainee': trainee})


@login_required
def details(request, pk):
    trainee = get_object_or_404(Trainee, pk=pk)

    fee_record = getattr(trainee, 'fee_record', None)

    base_fee = trainee.course.fee if trainee.course else 0

    # IMPORTANT: adjust this depending on your model
    discount = getattr(trainee, 'discount', 0)  # most likely correct

    final_fee = max(base_fee - discount, 0)

    paid = fee_record.total_paid() if fee_record else 0
    remaining = fee_record.remaining() if fee_record else 0

    return render(request, 'trainee_detail.html', {
        'trainee': trainee,
        'fee_record': fee_record,
        'base_fee': base_fee,
        'discount': discount,
        'final_fee': final_fee,
        'paid': paid,
        'remaining': remaining,
    })


# ---- AJAX ----
def ajax_course_fee(request):
    """Returns the fee for a given course as JSON. Used by the registration form."""
    course_id = request.GET.get('course_id')
    if course_id:
        try:
            course = Course.objects.get(pk=course_id)
            return JsonResponse({'fee': str(course.fee)})
        except Course.DoesNotExist:
            pass
    return JsonResponse({'fee': '0'})