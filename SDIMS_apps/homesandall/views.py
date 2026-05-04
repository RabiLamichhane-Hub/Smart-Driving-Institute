from datetime import date

from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

from SDIMS_apps.courses.models import Course
from SDIMS_apps.instructors.models import Instructor
from SDIMS_apps.vehicles.models import Vehicle
from SDIMS_apps.trainees.models import Trainee
from SDIMS_apps.accounts.decorators import role_required
from SDIMS_apps.scheduling.models import (
    Session,
    RescheduleQueue,
    SchedulingConfig,
    TraineePreference,
)

User = get_user_model()


def index(request):
    if request.user.is_authenticated:

        if request.user.is_superuser:
            return redirect('homesandall:admin_dashboard')

        if hasattr(request.user, 'instructor'):
            return redirect('homesandall:instructor_dashboard')

        return redirect('homesandall:trainee_dashboard')

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
    if request.user.role != 'admin':
        return redirect('accounts:login')

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

    return render(request, 'admin_dashboard.html', {
        # General
        'total_users':       total_users,
        'total_instructors': total_instructors,
        'total_trainees':    total_trainees,
        'active_trainees':   active_trainees,
        'recent_users':      recent_users,
        # Scheduling
        'pending_sessions_count':  pending_sessions_count,
        'todays_sessions_count':   todays_sessions_count,
        'reschedule_queue_count':  reschedule_queue_count,
        'flagged_count':           flagged_count,
    })


# ---------------------------------------------------------------------------
# INSTRUCTOR DASHBOARD
# ---------------------------------------------------------------------------

@login_required
@role_required(['instructor', 'supervisor'])
def instructor_dashboard(request):
    if not hasattr(request.user, 'instructor'):
        return redirect('homesandall:index')

    instructor = request.user.instructor
    trainees   = Trainee.objects.all()

    return render(request, 'instructor_dashboard.html', {
        'instructor': instructor,
        'trainees':   trainees,
    })


# ---------------------------------------------------------------------------
# TRAINEE DASHBOARD
# ---------------------------------------------------------------------------

@login_required
def trainee_dashboard(request):
    if request.user.role != 'trainee':
        return redirect('accounts:login')

    trainee = request.user.trainee

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
        date__lte=date.today().replace(day=date.today().day + 7)
            if date.today().day + 7 <= 28
            else date.today(),   # safe fallback; use timedelta below
    ).exclude(status='cancelled').select_related(
        'slot', 'vehicle', 'track', 'instructor'
    ).order_by('date', 'slot__slot_number')

    # Safer: use timedelta for next 7 days
    from datetime import timedelta
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