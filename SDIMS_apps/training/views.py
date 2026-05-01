from django.shortcuts import render, get_object_or_404, redirect
from .models import TrainingSession, Attendance
from .forms import TrainingSessionForm, AttendanceForm

# LIST
def session_list(request):
    sessions = TrainingSession.objects.all()
    return render(request, 'session_list.html', {'sessions': sessions})

# CREATE
def session_create(request):
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('training:session_list')
    else:
        form = TrainingSessionForm()
    return render(request, 'session_form.html', {'form': form})

# UPDATE
def session_update(request, pk):
    session = get_object_or_404(TrainingSession, pk=pk)
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            return redirect('training:session_list')
    else:
        form = TrainingSessionForm(instance=session)
    return render(request, 'session_form.html', {'form': form})

# DELETE
def session_delete(request, pk):
    session = get_object_or_404(TrainingSession, pk=pk)
    if request.method == 'POST':
        session.delete()
        return redirect('training:session_list')
    return render(request, 'session_confirm_delete.html', {'session': session})

# MARK ATTENDANCE (Instructor or Admin only)
def mark_attendance(request, pk):
    session = get_object_or_404(TrainingSession, pk=pk)

    attendance, created = Attendance.objects.get_or_create(session=session)

    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=attendance)
        if form.is_valid():
            form.save()
            # Auto-complete the session when attendance is marked
            session.status = 'completed'
            session.save()
            return redirect('training:session_list')
    else:
        form = AttendanceForm(instance=attendance)

    return render(request, 'mark_attendance.html', {'form': form, 'session': session})

# VIEW ATTENDANCE LIST
def attendance_list(request):
    records = Attendance.objects.select_related(
        'session__trainee__user',
        'session__instructor__user',
    ).all()
    return render(request, 'attendance_list.html', {'records': records})