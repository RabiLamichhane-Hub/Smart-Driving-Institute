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
from SDIMS_apps.scheduling.models import AttendanceRecord

User = get_user_model()

@login_required
@role_required(['admin', 'supervisor'])
def register(request):
    if request.method == 'POST':
        user_form = CreateUserForm(request.POST)
        trainee_form = TraineeForm(request.POST, request.FILES)

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

@login_required
@role_required(['admin', 'supervisor', 'instructor'])
def trainee_list(request):
    trainees = Trainee.objects.all()
    return render(request, 'trainee_list.html', {'trainees': trainees})


@login_required
@role_required(['admin', 'supervisor'])
def trainee_edit(request, pk):
    trainee = get_object_or_404(Trainee, pk=pk)

    if request.method == 'POST':
        trainee_form = TraineeForm(request.POST, request.FILES, instance=trainee)

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
@role_required(['admin', 'supervisor'])
def trainee_delete(request, pk):
    trainee = get_object_or_404(Trainee, pk=pk)
    if request.method == 'POST':
        trainee.user.delete()
        messages.success(request, "Trainee deleted successfully.")
        return redirect('trainees:trainee_list')

    return render(request, 'trainee_confirm_delete.html', {'trainee': trainee})


@login_required
@role_required(['admin', 'supervisor', 'instructor'])
def details(request, pk):
    trainee = get_object_or_404(Trainee, pk=pk)

    fee_record = getattr(trainee, 'fee_record', None)

    base_fee = trainee.course.fee if trainee.course else 0
    discount = getattr(trainee, 'discount', 0)
    final_fee = max(base_fee - discount, 0)

    paid = fee_record.total_paid() if fee_record else 0
    remaining = fee_record.remaining() if fee_record else 0

    payments = fee_record.payments.select_related('received_by').all() if fee_record else []

    # Attendance history: one AttendanceRecord per completed Session
    attendance_records = (
        AttendanceRecord.objects
        .filter(session__trainee=trainee)
        .select_related(
            'session',
            'session__slot',
            'session__track',
            'session__instructor',
            'session__supervisor',
            'marked_by',
        )
        .order_by('-session__date', '-session__slot__slot_number')
    )

    # Lesson progress (course trainees only)
    total_lessons     = trainee.course.total_lessons if trainee.course else 0
    lessons_attended  = (
        AttendanceRecord.objects.filter(
            session__trainee=trainee,
            status__in=['present', 'late'],
        ).count()
        if trainee.course else 0
    )
    lessons_remaining = max(total_lessons - lessons_attended, 0)

    # Summary counts for the attendance snapshot bar
    total_sessions   = attendance_records.count()
    present_count    = attendance_records.filter(status='present').count()
    late_count       = attendance_records.filter(status='late').count()
    absent_count     = attendance_records.filter(status='absent').count()
    attendance_rate  = (
        round((present_count + late_count) / total_sessions * 100)
        if total_sessions else 0
    )

    return render(request, 'trainee_detail.html', {
        'trainee': trainee,
        'fee_record': fee_record,
        'base_fee': base_fee,
        'discount': discount,
        'final_fee': final_fee,
        'paid': paid,
        'remaining': remaining,
        'payments': payments,
        # lesson progress
        'total_lessons':      total_lessons,
        'lessons_attended':   lessons_attended,
        'lessons_remaining':  lessons_remaining,
        # attendance
        'attendance_records': attendance_records,
        'total_sessions': total_sessions,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'attendance_rate': attendance_rate,
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