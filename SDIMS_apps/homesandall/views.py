from datetime import date, timedelta

from django.db.models import Count, Q
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from SDIMS_apps.courses.models import Course
from SDIMS_apps.instructors.models import Instructor
from SDIMS_apps.vehicles.models import Vehicle
from SDIMS_apps.trainees.models import Trainee
from SDIMS_apps.accounts.decorators import role_required, get_dashboard_url
from SDIMS_apps.scheduling.models import (
    Session,
    RescheduleQueue,
    RescheduleRequest,
    SchedulingConfig,
    TraineePreference,
)

User = get_user_model()


def index(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('homesandall:admin_dashboard')
            
        dashboard_url = get_dashboard_url(request.user)
        if dashboard_url == 'login':
            return redirect('accounts:login')
        return redirect(dashboard_url)

    courses     = Course.objects.all()
    instructors = Instructor.objects.select_related('user')
    vehicles    = Vehicle.objects.all()

    return render(request, 'index.html', {
        'courses':     courses,
        'instructors': instructors,
        'vehicles':    vehicles,
    })


# ---------------------------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------------------------

@login_required
@role_required(['admin'])
def admin_dashboard(request):
    # General stats
    total_users      = User.objects.count()
    total_instructors = Instructor.objects.count()
    total_trainees   = Trainee.objects.count()
    active_trainees  = Trainee.objects.filter(
        status__in=['ENROLLED', 'TRAINING']
    ).count()
    recent_users = User.objects.order_by('-id')[:5]

    # Scheduling stats
    config = SchedulingConfig.load()
    pending_sessions_count = Session.objects.filter(
        status='pending'
    ).count()
    todays_sessions_count = Session.objects.filter(
        date=date.today()
    ).exclude(status='cancelled').count()
    reschedule_queue_count = RescheduleQueue.objects.filter(
        resolved=False,
        attempt_count__lt=config.max_reschedule_attempts,
    ).count()
    flagged_count = RescheduleQueue.objects.filter(
        resolved=False,
        attempt_count__gte=config.max_reschedule_attempts,
    ).count()
    reschedule_requests_count = RescheduleRequest.objects.filter(
        status='pending'
    ).count()

    return render(request, 'admin_dashboard.html', {
        # General
        'total_users':       total_users,
        'total_instructors': total_instructors,
        'total_trainees':    total_trainees,
        'active_trainees':   active_trainees,
        'recent_users':      recent_users,
        # Scheduling
        'pending_sessions_count':    pending_sessions_count,
        'todays_sessions_count':     todays_sessions_count,
        'reschedule_queue_count':    reschedule_queue_count,
        'flagged_count':             flagged_count,
        'reschedule_requests_count': reschedule_requests_count,
    })


# ---------------------------------------------------------------------------
# INSTRUCTOR DASHBOARD
# ---------------------------------------------------------------------------

@login_required
@role_required(['instructor'])
def instructor_dashboard(request):
    if not hasattr(request.user, 'instructor'):
        return redirect('homesandall:index')

    instructor = request.user.instructor
    trainees   = Trainee.objects.all()

    return render(request, 'instructor_dashboard.html', {
        'instructor': instructor,
        'trainees':   trainees,
    })

@login_required
@role_required(['supervisor'])
def supervisor_dashboard(request):
    today = date.today()

    # ── Trainee counts ──────────────────────────────
    total_trainees  = Trainee.objects.count()
    active_trainees = Trainee.objects.filter(status__in=['ENROLLED', 'TRAINING']).count()

    # ── Today's sessions ────────────────────────────
    todays_sessions = (
        Session.objects
        .filter(date=today)
        .exclude(status='cancelled')
        .select_related('trainee__user', 'instructor__user', 'slot', 'vehicle', 'track')
        .order_by('slot__slot_number')
    )
    sessions_today          = todays_sessions.count()
    sessions_completed_today = todays_sessions.filter(status='completed').count()
    sessions_remaining_today = todays_sessions.exclude(status='completed').count()

    # ── Pending approvals ────────────────────────────
    pending_count = Session.objects.filter(status='pending').count()

    # ── Reschedule queue ─────────────────────────────
    config = SchedulingConfig.load()
    reschedule_queue_count = RescheduleQueue.objects.filter(
        resolved=False,
        attempt_count__lt=config.max_reschedule_attempts,
    ).count()

    # ── Instructor performance (this month) ──────────
    month_start = today.replace(day=1)
    instructors_qs = Instructor.objects.select_related('user').annotate(
        sessions_this_month=Count(
            'sessions',
            filter=Q(
                sessions__date__gte=month_start,
                sessions__date__lte=today,
            )
        )
    ).order_by('-sessions_this_month')[:5]

    max_sessions = max((i.sessions_this_month for i in instructors_qs), default=1) or 1
    for inst in instructors_qs:
        inst.sessions_pct = round(inst.sessions_this_month / max_sessions * 100)

    # ── Vehicle fleet status ─────────────────────────
    total_vehicles   = Vehicle.objects.count()
    vehicles_on_duty = Vehicle.objects.filter(status='in_use').count()
    reschedule_requests_count = RescheduleRequest.objects.filter(
        status='pending'
    ).count()

    return render(request, 'supervisor_dashboard.html', {
        # Trainee stats
        'total_trainees':          total_trainees,
        'active_trainees':         active_trainees,
        # Session stats
        'todays_sessions':         todays_sessions,
        'sessions_today':          sessions_today,
        'sessions_completed_today': sessions_completed_today,
        'sessions_remaining_today': sessions_remaining_today,
        # Approvals & reschedule
        'pending_count':              pending_count,
        'reschedule_queue_count':     reschedule_queue_count,
        'reschedule_requests_count':  reschedule_requests_count,
        # Instructors
        'top_instructors':         instructors_qs,
        # Vehicles
        'total_vehicles':          total_vehicles,
        'vehicles_on_duty':        vehicles_on_duty,
    })


# ---------------------------------------------------------------------------
# TRAINEE DASHBOARD
# ---------------------------------------------------------------------------

@login_required
@role_required(['trainee'])
def trainee_dashboard(request):
    try:
        trainee = request.user.trainee
    except Trainee.DoesNotExist:
        messages.error(request, "Your trainee profile is incomplete. Please contact the admin.")
        return redirect('accounts:login')

    # Payment info
    fee_record = getattr(trainee, 'fee_record', None)
    paid       = fee_record.total_paid()      if fee_record else 0
    remaining  = fee_record.remaining()       if fee_record else 0
    discount   = fee_record.discount_amount   if fee_record else 0
    final_fee  = fee_record.final_fee()       if fee_record else 0

    # Upcoming sessions (next 7 days, not cancelled)
    upcoming_sessions = Session.objects.filter(
        trainee=trainee,
        date__gte=date.today(),
        date__lte=date.today() + timedelta(days=7),
    ).exclude(status='cancelled').select_related(
        'slot', 'vehicle', 'track', 'instructor'
    ).order_by('date', 'slot__slot_number')

    # Current slot preferences
    slot_preferences = TraineePreference.objects.filter(
        trainee=trainee,
    ).select_related('slot').order_by('priority')

    return render(request, 'trainee_dashboard.html', {
        # Profile & payment
        'trainee':    trainee,
        'fee_record': fee_record,
        'paid':       paid,
        'remaining':  remaining,
        'discount':   discount,
        'final_fee':  final_fee,
        # Scheduling
        'upcoming_sessions': upcoming_sessions,
        'slot_preferences':  slot_preferences,
    })