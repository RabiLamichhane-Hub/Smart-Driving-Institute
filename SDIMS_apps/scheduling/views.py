"""
scheduling/views.py

All views for the Scheduling & Attendance module.

URL map (see urls.py):
  GET/POST  /scheduling/preferences/              → TraineePreferenceView
  GET       /scheduling/my-schedule/              → MyScheduleView
  GET       /scheduling/sessions/                 → SessionListView          (supervisor+)
  GET/POST  /scheduling/approve/                  → ApproveScheduleView      (supervisor+)
  POST      /scheduling/approve/<pk>/             → ApproveSingleSessionView (supervisor+)
  POST      /scheduling/cancel/<pk>/              → CancelSessionView        (supervisor+)
  GET/POST  /scheduling/attendance/today/         → AttendanceTodayView      (supervisor+)
  GET       /scheduling/attendance/history/       → AttendanceHistoryView    (supervisor+)
  GET       /scheduling/reschedule/queue/         → RescheduleQueueView      (supervisor+)
  GET/POST  /scheduling/reschedule/flagged/       → FlaggedRescheduleView    (admin)
  POST      /scheduling/run-scheduler/            → RunSchedulerView         (supervisor+)
  GET       /scheduling/runs/                     → ScheduleRunListView      (supervisor+)
  GET       /scheduling/runs/<pk>/                → ScheduleRunDetailView    (supervisor+)
"""

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import localdate
from django.utils.decorators import method_decorator
from django.views import View

from .models import (
    AttendanceRecord,
    DailyScheduleRun,
    RescheduleQueue,
    SchedulingConfig,
    Session,
    TimeSlot,
    TraineePreference,
)
from .scheduler import run_scheduler

# Reuse the decorators already defined in accounts app
from SDIMS_apps.accounts.decorators import role_required
import logging
logger = logging.getLogger(__name__)


# 1. Trainee Preference View

@method_decorator(login_required, name='dispatch')
class TraineePreferenceView(View):
    """
    Trainees set their ranked slot preferences here.
    GET  → show current preferences with all 6 slots
    POST → clear old preferences and save new ranked list
    """
    template_name = 'preferences.html'

    def get(self, request):
        if request.user.role != 'trainee':
            messages.error(request, "Only trainees can set slot preferences.")
            return redirect('homesandall:trainee_dashboard')

        slots   = TimeSlot.objects.order_by('slot_number')
        current = TraineePreference.objects.filter(
            trainee=request.user.trainee
        ).select_related('slot').order_by('priority')

        return render(request, self.template_name, {
            'slots':   slots,
            'current': current,
        })

    def post(self, request):
        if request.user.role != 'trainee':
            messages.error(request, "Only trainees can set slot preferences.")
            return redirect('accounts:trainee_dashboard')

        trainee  = request.user.trainee
        slot_ids = request.POST.getlist('slot_order')

        if not slot_ids:
            messages.error(request, "Please select at least one preferred slot.")
            return redirect('scheduling:preferences')

        with transaction.atomic():
            TraineePreference.objects.filter(trainee=trainee).delete()
            preferences = []
            for priority, slot_id in enumerate(slot_ids, start=1):
                try:
                    slot = TimeSlot.objects.get(pk=slot_id)
                    preferences.append(
                        TraineePreference(
                            trainee=trainee, slot=slot, priority=priority
                        )
                    )
                except TimeSlot.DoesNotExist:
                    continue
            TraineePreference.objects.bulk_create(preferences)

        messages.success(request, "Your slot preferences have been saved.")
        return redirect('scheduling:preferences')


# 2. My Schedule View  (all roles)

@login_required
def my_schedule_view(request):
    """
    Shows upcoming scheduled sessions for the logged-in user.
    - Trainee    → their own sessions
    - Instructor → sessions where they are the instructor
    - Supervisor / Admin → redirected to full session list
    """
    role = request.user.role
    today = localdate()
 
    if role == 'trainee':
        sessions = (
            Session.objects
            .filter(trainee=request.user.trainee, date__gte=today)
            .exclude(status='cancelled')
            .select_related('slot', 'vehicle', 'instructor', 'track')
            .order_by('date', 'slot__slot_number')
        )
        trainee_count = None
 
    elif role == 'instructor':
        sessions = (
            Session.objects
            .filter(instructor=request.user.instructor, date__gte=today)
            .exclude(status='cancelled')
            .select_related('slot', 'trainee', 'vehicle', 'track')
            .order_by('date', 'slot__slot_number')
        )
        # distinct trainees across upcoming sessions
        trainee_count = (
            sessions
            .values('trainee')
            .distinct()
            .count()
        )
 
    else:
        # Supervisors and admins use the full session list view
        return redirect('scheduling:session_list')
 
    today_count = sum(1 for s in sessions if s.date == today)
 
    return render(request, 'my_schedule.html', {
        'sessions': sessions,
        'role': role,
        'today_count': today_count,
        'trainee_count': trainee_count,
    })


# 3. Session List View  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor', 'instructor'])
def session_list_view(request):
    """
    Full paginated session list with filters for date, status, slot, trainee type.
    """
    sessions = Session.objects.select_related(
        'trainee__user',
        'instructor__user',
        'slot',
        'vehicle',
        'track',
        'supervisor',
    ).order_by('-date', 'slot__slot_number')

    filter_date   = request.GET.get('date', '').strip()
    filter_status = request.GET.get('status', '').strip()
    filter_slot   = request.GET.get('slot', '').strip()
    filter_type   = request.GET.get('trainee_type', '').strip()

    if filter_date:
        sessions = sessions.filter(date=filter_date)
    if filter_status:
        sessions = sessions.filter(status=filter_status)
    if filter_slot:
        sessions = sessions.filter(slot_id=filter_slot)
    if filter_type:
        sessions = sessions.filter(trainee_type=filter_type)

    logger.debug("Filters — date=%s status=%s slot=%s type=%s | count=%s",
                 filter_date, filter_status, filter_slot, filter_type,
                 sessions.count())

    paginator = Paginator(sessions, 25)
    page      = paginator.get_page(request.GET.get('page'))

    return render(request, 'session_list.html', {
        'page':           page,
        'slots':          TimeSlot.objects.all(),
        'status_choices': Session.STATUS_CHOICES,
        'type_choices':   Session.TRAINEE_TYPE_CHOICES,
        'filter_date':    filter_date,
        'filter_status':  filter_status,
        'filter_slot':    filter_slot,
        'filter_type':    filter_type,
    })


# 4. Approve Schedule View  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def approve_schedule_view(request):
    pending = Session.objects.filter(
        status='pending'
    ).select_related('trainee', 'slot', 'vehicle', 'instructor', 'track'
    ).order_by('date', 'slot__slot_number')  # order by date first

    # Group by date → slot
    grouped_by_date = {}
    for session in pending:
        session_date = session.date  # adjust if your field is named differently
        grouped_by_date.setdefault(session_date, {})
        grouped_by_date[session_date].setdefault(session.slot, []).append(session)

    if request.method == 'POST':
        selected_ids = request.POST.getlist('session_ids')
        approved = 0
        with transaction.atomic():
            for pk in selected_ids:
                try:
                    session = Session.objects.get(pk=pk, status='pending')
                    session.approve(request.user)
                    approved += 1
                except (Session.DoesNotExist, Exception):
                    continue

        messages.success(request, f"{approved} session(s) approved.")
        return redirect('scheduling:approve')

    return render(request, 'approve_schedule.html', {
        'grouped_by_date': grouped_by_date,
        'total': pending.count(),
    })


# 5. Approve Single Session  (supervisor / admin) — AJAX-friendly

@login_required
@role_required(['admin', 'supervisor'])
def approve_single_session_view(request, pk):
    """POST only. Approves a single pending session. Returns JSON if AJAX."""
    if request.method != 'POST':
        return redirect('scheduling:approve')

    session = get_object_or_404(Session, pk=pk)
    try:
        session.approve(request.user)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok', 'session_id': pk})
        messages.success(request, f"Session #{pk} approved.")
    except Exception as exc:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'detail': str(exc)}, status=400)
        messages.error(request, str(exc))

    return redirect('scheduling:approve')


# 6. Cancel Session  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def cancel_session_view(request, pk):
    """POST only. Cancels a session that is not yet completed."""
    if request.method != 'POST':
        return redirect('scheduling:session_list')

    session = get_object_or_404(Session, pk=pk)
    try:
        session.cancel()
        messages.success(request, f"Session #{pk} cancelled.")
    except Exception as exc:
        messages.error(request, str(exc))

    return redirect(request.POST.get('next', 'scheduling:session_list'))


# 7. Attendance Today View  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def attendance_today_view(request):
    """
    GET  → List today's scheduled/ongoing sessions ready for attendance.
    POST → Save attendance records for submitted sessions.
    """
    today = date.today()
    sessions = Session.objects.filter(
        date=today,
        status__in=('scheduled', 'ongoing', 'completed'),
    ).select_related(
        'trainee', 'slot', 'vehicle', 'instructor'
    ).order_by('slot__slot_number')

    existing_attendance = {
        a.session_id: a
        for a in AttendanceRecord.objects.filter(
            session__date=today
        ).select_related('session')
    }

    if request.method == 'POST':
        saved  = 0
        errors = []

        with transaction.atomic():
            for session in sessions:
                status_key = f'status_{session.pk}'
                notes_key  = f'notes_{session.pk}'
                status     = request.POST.get(status_key)
                notes      = request.POST.get(notes_key, '').strip()

                if not status:
                    continue

                if status not in ('present', 'late', 'absent'):
                    errors.append(f"Invalid status for session #{session.pk}.")
                    continue

                record, created = AttendanceRecord.objects.get_or_create(
                    session=session,
                    defaults={
                        'status':    status,
                        'marked_by': request.user,
                        'notes':     notes,
                    },
                )
                if not created:
                    record.status    = status
                    record.notes     = notes
                    record.marked_by = request.user
                    record.save(update_fields=['status', 'notes', 'marked_by'])

                saved += 1

        if errors:
            for e in errors:
                messages.warning(request, e)
        messages.success(request, f"Attendance saved for {saved} session(s).")
        return redirect('scheduling:attendance_today')

    # Annotate each session with its existing attendance status/notes
    # so the template can render checked radios and pre-filled notes
    # without needing a custom template filter.
    sessions = list(sessions)
    for session in sessions:
        record = existing_attendance.get(session.pk)
        session.att_status = record.status if record else ''
        session.att_notes  = record.notes  if record else ''

    return render(request, 'attendance_today.html', {
        'sessions': sessions,
        'today':    today,
    })


# 8. Attendance History View  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def attendance_history_view(request):
    """Filterable attendance history across all dates."""
    records = AttendanceRecord.objects.select_related(
        'session__trainee', 'session__slot', 'marked_by'
    ).order_by('-session__date', 'session__slot__slot_number')

    filter_date    = request.GET.get('date')
    filter_status  = request.GET.get('status')
    filter_trainee = request.GET.get('trainee')

    if filter_date:
        records = records.filter(session__date=filter_date)
    if filter_status:
        records = records.filter(status=filter_status)
    if filter_trainee:
        records = records.filter(
            session__trainee__user__first_name__icontains=filter_trainee
        ) | records.filter(
            session__trainee__user__last_name__icontains=filter_trainee
        )

    paginator = Paginator(records, 30)
    page      = paginator.get_page(request.GET.get('page'))

    return render(request, 'attendance_history.html', {
        'page':           page,
        'status_choices': AttendanceRecord.STATUS_CHOICES,
        'filter_date':    filter_date,
        'filter_status':  filter_status,
        'filter_trainee': filter_trainee,
    })


# 9. Reschedule Queue View  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def reschedule_queue_view(request):
    """Shows all unresolved reschedule queue entries under the attempt limit."""
    queue = RescheduleQueue.objects.filter(
        resolved=False,
        attempt_count__lt=SchedulingConfig.load().max_reschedule_attempts,
    ).select_related(
        'trainee', 'original_session__slot'
    ).order_by('priority', '-priority_score', 'attempt_count', 'added_at')

    if request.method == 'POST':
        entry_id     = request.POST.get('entry_id')
        new_priority = request.POST.get('priority')
        if entry_id and new_priority:
            try:
                entry          = RescheduleQueue.objects.get(pk=entry_id)
                entry.priority = int(new_priority)
                entry.save(update_fields=['priority'])
                messages.success(request, f"Priority updated for {entry.trainee}.")
            except (RescheduleQueue.DoesNotExist, ValueError):
                messages.error(request, "Could not update priority.")
        return redirect('scheduling:reschedule_queue')

    return render(request, 'reschedule_queue.html', {
        'queue':          queue,
        'priority_range': range(1, 6),
    })


# 10. Flagged Reschedule View  (admin only)

@login_required
@role_required(['admin'])
def flagged_reschedule_view(request):
    """Reschedule entries that hit the max attempt limit — admin intervenes."""
    config  = SchedulingConfig.load()
    flagged = RescheduleQueue.objects.filter(
        resolved=False,
        attempt_count__gte=config.max_reschedule_attempts,
    ).select_related('trainee', 'original_session__slot')

    if request.method == 'POST':
        action   = request.POST.get('action')
        entry_id = request.POST.get('entry_id')

        try:
            entry = RescheduleQueue.objects.get(pk=entry_id)
        except RescheduleQueue.DoesNotExist:
            messages.error(request, "Queue entry not found.")
            return redirect('scheduling:flagged_reschedule')

        if action == 'reset':
            entry.attempt_count  = 0
            entry.priority_score = 0
            entry.priority       = 1
            entry.save(update_fields=['attempt_count', 'priority_score', 'priority'])
            messages.success(
                request,
                f"Attempt counter reset for {entry.trainee}. "
                "Will be retried in the next scheduler run."
            )

        elif action == 'manual_resolve':
            session_id = request.POST.get('session_id')
            try:
                session = Session.objects.get(pk=session_id)
                entry.resolve(session)
                messages.success(
                    request,
                    f"Manually resolved {entry.trainee} → Session #{session_id}."
                )
            except Session.DoesNotExist:
                messages.error(request, "Session not found.")

        return redirect('scheduling:flagged_reschedule')

    return render(request, 'flagged_reschedule.html', {
        'flagged':           flagged,
        'upcoming_sessions': Session.objects.filter(
            date__gte=date.today(), status__in=('pending', 'scheduled')
        ).select_related('trainee', 'slot').order_by('date', 'slot__slot_number'),
    })


# 11. Run Scheduler View  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def run_scheduler_view(request):
    """POST only. Manually triggers the scheduler for tomorrow (or a given date)."""
    if request.method != 'POST':
        return redirect('scheduling:run_list')

    config      = SchedulingConfig.load()
    target_date = date.today() + timedelta(days=config.schedule_days_ahead)

    if request.user.role == 'admin':
        override = request.POST.get('target_date')
        if override:
            try:
                from datetime import datetime
                target_date = datetime.strptime(override, '%Y-%m-%d').date()
            except ValueError:
                pass

    run = run_scheduler(target_date, triggered_by=request.user)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'run_id':           run.pk,
            'target_date':      str(run.run_date),
            'sessions_created': run.sessions_created,
            'notes':            run.notes,
        })

    messages.success(
        request,
        f"Scheduler completed for {run.run_date}. "
        f"{run.sessions_created} session(s) created."
    )
    if run.notes:
        messages.warning(request, f"Scheduler notes: {run.notes[:300]}")

    return redirect('scheduling:run_detail', pk=run.pk)


@login_required
@role_required(['admin', 'supervisor'])
def run_scheduler_bulk_view(request):
    """
    POST only. Schedules multiple consecutive days in one go.
    Accepts 'days' param (default 7, max 90).
    Skips days that already have sessions scheduled.
    Returns a summary of all runs.
    """
    if request.method != 'POST':
        return redirect('scheduling:run_list')
 
    try:
        days = int(request.POST.get('days', 7))
        days = max(1, min(days, 90))   # clamp between 1 and 90
    except ValueError:
        days = 7
 
    start_date     = date.today() + timedelta(days=1)
    total_sessions = 0
    skipped_days   = 0
    run_ids        = []
 
    for i in range(days):
        target = start_date + timedelta(days=i)
 
        # Skip days that already have sessions to avoid duplicates
        already_has_sessions = Session.objects.filter(date=target).exclude(
            status='cancelled'
        ).exists()
 
        if already_has_sessions:
            skipped_days += 1
            continue
 
        run = run_scheduler(target, triggered_by=request.user)
        total_sessions += run.sessions_created
        run_ids.append(run.pk)
 
    scheduled_days = days - skipped_days
 
    messages.success(
        request,
        f"Bulk scheduler completed: {scheduled_days} day(s) scheduled, "
        f"{total_sessions} total session(s) created."
        + (f" {skipped_days} day(s) skipped (already had sessions)." if skipped_days else "")
    )
 
    # If only one run was created go straight to its detail page
    if len(run_ids) == 1:
        return redirect('scheduling:run_detail', pk=run_ids[0])
 
    return redirect('scheduling:run_list')


# 12. Schedule Run List  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def schedule_run_list_view(request):
    """Audit log of all scheduler runs."""
    runs      = DailyScheduleRun.objects.select_related('triggered_by').order_by('-ran_at')
    paginator = Paginator(runs, 20)
    page      = paginator.get_page(request.GET.get('page'))

    return render(request, 'run_list.html', {'page': page})


# 13. Schedule Run Detail  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def schedule_run_detail_view(request, pk):
    """Detail view for a single scheduler run — shows all sessions it created."""
    run = get_object_or_404(DailyScheduleRun, pk=pk)
    sessions = run.sessions.select_related(
        'trainee', 'slot', 'vehicle', 'instructor', 'track'
    ).order_by('slot__slot_number')

    return render(request, 'run_detail.html', {
        'run':      run,
        'sessions': sessions,
    })