"""
scheduling/views.py

All views for the Scheduling & Attendance module.

URL map (see urls.py):
  GET/POST  /scheduling/preferences/                        → TraineePreferenceView
  GET       /scheduling/my-schedule/                        → my_schedule_view
  GET       /scheduling/sessions/                           → session_list_view          (supervisor+)
  GET/POST  /scheduling/approve/                            → approve_schedule_view      (supervisor+)
  POST      /scheduling/approve/<pk>/                       → approve_single_session_view (supervisor+)
  POST      /scheduling/cancel/<pk>/                        → cancel_session_view        (supervisor+)
  GET/POST  /scheduling/attendance/today/                   → attendance_today_view      (supervisor+)
  GET       /scheduling/attendance/history/                 → attendance_history_view    (supervisor+)
  GET       /scheduling/reschedule/queue/                   → reschedule_queue_view      (supervisor+)
  GET/POST  /scheduling/reschedule/flagged/                 → flagged_reschedule_view    (admin)
  GET/POST  /scheduling/reschedule/request/<session_pk>/   → trainee_reschedule_request_view  (trainee)
  GET/POST  /scheduling/reschedule/requests/               → reschedule_requests_view   (supervisor+)
  POST      /scheduling/run-scheduler/                      → run_scheduler_view         (supervisor+)
  GET       /scheduling/runs/                               → schedule_run_list_view     (supervisor+)
  GET       /scheduling/runs/<pk>/                          → schedule_run_detail_view   (supervisor+)
"""

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import localdate, now
from django.utils.decorators import method_decorator
from django.views import View

from .models import (
    AttendanceRecord,
    DailyScheduleRun,
    RescheduleQueue,
    RescheduleRequest,
    SchedulingConfig,
    Session,
    TimeSlot,
    TraineePreference,
)
from .forms import RescheduleRequestForm
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
    - Trainee    → their own sessions + pending_request_session_ids for the button logic
    - Instructor → sessions where they are the instructor
    - Supervisor / Admin → redirected to full session list
    """
    role  = request.user.role
    today = localdate()

    # Statuses that mean the session is over — never show in "upcoming"
    TERMINAL_STATUSES = ['cancelled', 'absent']

    if role == 'trainee':
        sessions = (
            Session.objects
            .filter(trainee=request.user.trainee, date__gte=today)
            .exclude(status__in=TERMINAL_STATUSES)
            .select_related('slot', 'vehicle', 'instructor', 'track')
            .order_by('date', 'slot__slot_number')
        )
        trainee_count = None

        # Build a set of session IDs that already have a pending reschedule
        # request — the template uses this to show "Requested" vs the button.
        pending_request_session_ids = set(
            RescheduleRequest.objects.filter(
                trainee=request.user.trainee,
                status='pending',
            ).values_list('session_id', flat=True)
        )

    elif role == 'instructor':
        sessions = (
            Session.objects
            .filter(instructor=request.user.instructor, date__gte=today)
            .exclude(status__in=TERMINAL_STATUSES)
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
        pending_request_session_ids = set()

    else:
        # Supervisors and admins use the full session list view
        return redirect('scheduling:session_list')

    today_count = sum(1 for s in sessions if s.date == today)

    return render(request, 'my_schedule.html', {
        'sessions':                    sessions,
        'role':                        role,
        'today_count':                 today_count,
        'trainee_count':               trainee_count,
        'pending_request_session_ids': pending_request_session_ids,
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
        session_date = session.date
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
        entry_id = request.POST.get('entry_id')
        new_priority = request.POST.get('priority')
        if entry_id and new_priority:
            try:
                entry = RescheduleQueue.objects.get(pk=entry_id)
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


# 11. Trainee Reschedule Request View  (trainee-facing)

@login_required
def trainee_reschedule_request_view(request, session_pk):
    """
    Trainee submits a request to reschedule a specific upcoming session.

    GET  → Show session details + optional reason textarea.
    POST → Validate and create a RescheduleRequest with status='pending'.
    """
    if request.user.role != 'trainee':
        messages.error(request, "Only trainees can request a reschedule.")
        return redirect('scheduling:my_schedule')

    trainee = request.user.trainee
    session = get_object_or_404(Session, pk=session_pk, trainee=trainee)

    # Guard: session must be in a reschedulable state.
    if session.status not in ('scheduled', 'pending'):
        messages.error(
            request,
            f"This session cannot be rescheduled — its status is '{session.get_status_display()}'."
        )
        return redirect('scheduling:my_schedule')

    # Guard: no duplicate pending request for the same session.
    already_requested = RescheduleRequest.objects.filter(
        trainee=trainee,
        session=session,
        status='pending',
    ).exists()

    if already_requested:
        messages.warning(
            request,
            "You already have a pending reschedule request for this session."
        )
        return redirect('scheduling:my_schedule')

    if request.method == 'POST':
        form = RescheduleRequestForm(request.POST)
        if form.is_valid():
            reschedule_request = form.save(commit=False)
            reschedule_request.trainee = trainee
            reschedule_request.session = session
            reschedule_request.status  = 'pending'
            reschedule_request.save()

            messages.success(
                request,
                "Your reschedule request has been submitted. "
                "A supervisor will review it shortly."
            )
            return redirect('scheduling:my_schedule')
    else:
        form = RescheduleRequestForm()

    return render(request, 'reschedule_request_form.html', {
        'form':    form,
        'session': session,
    })


# 12. Reschedule Requests View  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def reschedule_requests_view(request):
    """
    Supervisor/admin interface to review trainee-initiated reschedule requests.

    GET  → Lists all pending requests; also shows resolved history below.
    POST → Approve or reject a specific request by ID.
          - approve: cancel original session + create RescheduleQueue entry.
          - reject:  save rejection note, leave session unchanged.
    """
    if request.method == 'POST':
        action     = request.POST.get('action')
        request_id = request.POST.get('request_id')

        try:
            rr = RescheduleRequest.objects.select_related(
                'trainee', 'session'
            ).get(pk=request_id, status='pending')
        except RescheduleRequest.DoesNotExist:
            messages.error(request, "Request not found or already resolved.")
            return redirect('scheduling:reschedule_requests')

        with transaction.atomic():
            if action == 'approve':
                # 1. Mark request approved.
                rr.status      = 'approved'
                rr.reviewed_by = request.user
                rr.reviewed_at = now()
                rr.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

                # 2. Cancel the original session.
                original_session = rr.session
                try:
                    original_session.cancel()
                except Exception as exc:
                    messages.error(
                        request,
                        f"Could not cancel session #{original_session.pk}: {exc}"
                    )
                    return redirect('scheduling:reschedule_requests')

                # 3. Create a RescheduleQueue entry so the scheduler picks them up.
                #    Priority 2 (High) — trainee proactively requested, signals intent.
                RescheduleQueue.objects.create(
                    trainee=rr.trainee,
                    original_session=original_session,
                    priority=2,
                )

                messages.success(
                    request,
                    f"Request approved. {rr.trainee}'s session has been cancelled "
                    "and they've been added to the reschedule queue."
                )

            elif action == 'reject':
                rejection_note = request.POST.get('rejection_note', '').strip()
                rr.status         = 'rejected'
                rr.reviewed_by    = request.user
                rr.reviewed_at    = now()
                rr.rejection_note = rejection_note
                rr.save(update_fields=[
                    'status', 'reviewed_by', 'reviewed_at', 'rejection_note'
                ])

                messages.success(
                    request,
                    f"Request from {rr.trainee} has been rejected. "
                    "Their original session remains unchanged."
                )

            else:
                messages.error(request, "Invalid action.")

        return redirect('scheduling:reschedule_requests')

    # GET — list pending requests and historical ones separately.
    pending_requests = RescheduleRequest.objects.filter(
        status='pending'
    ).select_related(
        'trainee__user', 'session__slot'
    ).order_by('created_at')

    resolved_requests = RescheduleRequest.objects.exclude(
        status='pending'
    ).select_related(
        'trainee__user', 'session__slot', 'reviewed_by'
    ).order_by('-reviewed_at')[:50]  # cap history at 50 rows

    return render(request, 'reschedule_requests.html', {
        'pending_requests':  pending_requests,
        'resolved_requests': resolved_requests,
    })


# 13. Run Scheduler View  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def run_scheduler_view(request):
    """POST only. Manually triggers the scheduler for tomorrow (or a given date)."""
    if request.method != 'POST':
        return redirect('scheduling:run_list')
    
    from .scheduler import is_working_day

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

    if not is_working_day(target_date):
        day_name = target_date.strftime('%A')
        messages.warning(
            request,
            f"{target_date} ({day_name}) is a non-working day. "
            "No sessions were scheduled. Choose a working day."
        )
        return redirect('scheduling:run_list')
    run = run_scheduler(target_date, triggered_by=request.user)
    if run is None:
        messages.warning(request, f"No sessions created — {target_date} is a day off.")
        return redirect('scheduling:run_list')

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
    if request.method != 'POST':
        return redirect('scheduling:run_list')
    from .scheduler import is_working_day   # import here to keep top clean
    try:
        days = int(request.POST.get('days', 7))
        days = max(1, min(days, 90))
    except ValueError:
        days = 7
    start_date       = date.today() + timedelta(days=1)
    total_sessions   = 0
    skipped_off_days = 0
    skipped_dup_days = 0
    run_ids          = []
    scheduled_count  = 0
    current = start_date
    while scheduled_count < days:
        # ── NEW: skip weekends & holidays ──
        if not is_working_day(current):
            skipped_off_days += 1
            current += timedelta(days=1)
            continue
        # Skip if already has sessions
        already_has_sessions = Session.objects.filter(
            date=current
        ).exclude(status='cancelled').exists()
        if already_has_sessions:
            skipped_dup_days += 1
            current += timedelta(days=1)
            continue
        run = run_scheduler(current, triggered_by=request.user)
        if run:
            total_sessions += run.sessions_created
            run_ids.append(run.pk)
        scheduled_count += 1
        current += timedelta(days=1)
    # Safety valve: if we somehow exhaust too many calendar days, stop
    # (shouldn't happen unless someone marks 90+ consecutive days as off)
    msg = (
        f"Bulk scheduler: {scheduled_count} working day(s) scheduled, "
        f"{total_sessions} session(s) created."
    )
    if skipped_off_days:
        msg += f" {skipped_off_days} weekend/holiday day(s) skipped."
    if skipped_dup_days:
        msg += f" {skipped_dup_days} day(s) skipped (already had sessions)."
    messages.success(request, msg)
    if len(run_ids) == 1:
        return redirect('scheduling:run_detail', pk=run_ids[0])
    return redirect('scheduling:run_list')


# 14. Schedule Run List  (supervisor / admin)

@login_required
@role_required(['admin', 'supervisor'])
def schedule_run_list_view(request):
    """Audit log of all scheduler runs."""
    runs      = DailyScheduleRun.objects.select_related('triggered_by').order_by('-ran_at')
    paginator = Paginator(runs, 20)
    page      = paginator.get_page(request.GET.get('page'))

    return render(request, 'run_list.html', {'page': page})


# 15. Schedule Run Detail  (supervisor / admin)

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

# 16. Day-Off Calendar  (admin / supervisor)
@login_required
@role_required(['admin', 'supervisor'])
def day_off_list_view(request):
    """
    GET  → Shows upcoming (future) day-off entries + a form to add a new one.
    POST → Declares a new day off (date + optional reason).
    """
    from .models import HolidayOrDayOff
    from django.core.exceptions import ValidationError as DjangoValidationError
    if request.method == 'POST':
        raw_date = request.POST.get('date', '').strip()
        reason   = request.POST.get('reason', '').strip()
        try:
            from datetime import datetime
            off_date = datetime.strptime(raw_date, '%Y-%m-%d').date()
            entry    = HolidayOrDayOff(
                date        = off_date,
                reason      = reason,
                declared_by = request.user,
            )
            entry.full_clean()   # runs the weekend guard in HolidayOrDayOff.clean()
            entry.save()
            deleted_count, _ = Session.objects.filter(
                date=off_date,
                status__in=['pending', 'scheduled']
            ).delete()
            messages.success(
                request,
                f"{off_date} has been marked as a day off. "
                f"{deleted_count} session(s) on that date have been removed."
            )
        except (ValueError, DjangoValidationError) as exc:
            err = exc.message_dict if hasattr(exc, 'message_dict') else str(exc)
            messages.error(request, f"Could not save day off: {err}")
        return redirect('scheduling:day_off_list')
    today      = date.today()
    upcoming   = HolidayOrDayOff.objects.filter(date__gte=today).order_by('date')
    past       = HolidayOrDayOff.objects.filter(date__lt=today).order_by('-date')[:20]
    return render(request, 'day_off_list.html', {
        'upcoming': upcoming,
        'past':     past,
        'today':    today,
    })


@login_required
@role_required(['admin', 'supervisor'])
def day_off_delete_view(request, pk):
    """POST only. Removes a declared day-off entry."""
    from .models import HolidayOrDayOff
    entry = get_object_or_404(HolidayOrDayOff, pk=pk)
    if request.method == 'POST':
        date_str = str(entry.date)
        entry.delete()
        messages.success(request, f"Day-off entry for {date_str} has been removed.")
    return redirect('scheduling:day_off_list')