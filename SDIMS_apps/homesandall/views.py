from datetime import date, datetime, timedelta
from collections import defaultdict

from django.db.models import Count, Q
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from SDIMS_apps.courses.models import Course
from SDIMS_apps.instructors.models import Instructor
from SDIMS_apps.vehicles.models import Vehicle
from SDIMS_apps.trainees.models import Trainee
from SDIMS_apps.accounting.models import Payment, SessionPayment, Expense, FeeRecord
from SDIMS_apps.accounts.decorators import role_required, get_dashboard_url
from SDIMS_apps.scheduling.models import (
    Session,
    RescheduleQueue,
    RescheduleRequest,
    SchedulingConfig,
    TraineePreference,
    PublicBooking,
    TimeSlot,
    Track,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _get_working_days_ahead(n=5):
    """
    Return the next n working days (Mon–Fri, not a declared holiday),
    starting from today.

    We fetch more days than needed (n + 3 buffer) so that after the
    booking-cutoff filter in _build_public_vacancy removes near-term
    slots, there are still enough days to fill the display grid.
    """
    from SDIMS_apps.scheduling.scheduler import is_working_day
    days  = []
    check = date.today()
    # Collect up to n+3 working days so the cutoff filter has room.
    target = n + 3
    while len(days) < target:
        if is_working_day(check):
            days.append(check)
        check += timedelta(days=1)
    return days


def _build_public_vacancy(target_dates, config=None):
    """
    For each date in target_dates, compute how many walk-in (independent)
    slots are still open per TimeSlot, broken down by vehicle category
    (4-wheeler = car, 2-wheeler = bike + scooter).

    Returns a list of dicts ordered by date then slot_number:
    [
      {
        'date':         date object,
        'date_display': 'Mon, 19 May',
        'is_today':     bool,
        'slots': [
          {
            'label':       '8:00 AM – 9:00 AM',
            'start_time':  time,
            'end_time':    time,
            'four_wheel':  2,   # remaining 4-wheeler spots  (0 = fully booked, shown greyed)
            'two_wheel':   1,   # remaining 2-wheeler spots  (0 = fully booked, shown greyed)
          },
          ...  (all slots within the booking cutoff window, including fully booked ones)
        ]
      },
      ...  (all days that have at least one slot within the cutoff window)
    ]
    """
    from SDIMS_apps.vehicles.models import Vehicle as VehicleModel
    from SDIMS_apps.instructors.models import Instructor as InstructorModel

    if config is None:
        config = SchedulingConfig.load()

    if not config.public_booking_enabled:
        return []

    slots = list(TimeSlot.objects.order_by('slot_number'))
    pct   = config.course_capacity_pct

    # ------------------------------------------------------------------ #
    # Compute per-category independent base capacity.                      #
    # Tracks and vehicles are typed, so we split the maths by category.   #
    # Instructors are shared across both categories — the same pool.       #
    # ------------------------------------------------------------------ #

    instructors_count = InstructorModel.objects.filter(status='active').count()

    car_vehicles = VehicleModel.objects.filter(
        status='available', vehicle_type='car'
    ).count()
    tw_vehicles  = VehicleModel.objects.filter(
        status='available', vehicle_type__in=('bike', 'scooter')
    ).count()

    car_tracks = Track.objects.filter(status='active', track_type='car').count()
    tw_tracks  = Track.objects.filter(status='active', track_type='two_wheeler').count()

    def _indep_base(track_cnt, vehicle_cnt, inst_cnt, capacity_pct):
        """
        Independent base capacity for one vehicle category.

        Uses int() (floor) — NOT round() — so the course reservation is
        always rounded DOWN.  round() was silently stealing capacity:
          1 vehicle, pct=0.70 → round(0.70)=1 reserved → 0 independent.
          1 vehicle, pct=0.70 →   int(0.70)=0 reserved → 1 independent. ✓
        """
        track_cap    = track_cnt * 2
        guided_total = min(track_cap, vehicle_cnt, inst_cnt)
        unguided     = min(track_cap, vehicle_cnt)
        reserved     = int(guided_total * capacity_pct) if guided_total > 0 else 0
        return max(0, unguided - reserved)

    car_base = _indep_base(car_tracks, car_vehicles, instructors_count, pct)
    tw_base  = _indep_base(tw_tracks,  tw_vehicles,  instructors_count, pct)

    # Nothing to display if the institute has no physical infrastructure at all.
    if car_base <= 0 and tw_base <= 0:
        return []

    now   = datetime.now()
    today = date.today()
    result = []

    for target_date in target_dates:
        # Per-slot remaining counters, one dict per vehicle category.
        car_remaining = {s.id: car_base for s in slots}
        tw_remaining  = {s.id: tw_base  for s in slots}

        # ── Deduct ALL existing sessions by vehicle type (course + independent) ── #
        existing_indep = (
            Session.objects
            .filter(date=target_date)
            .exclude(status='cancelled')
            .values('slot_id', 'vehicle__vehicle_type')
        )
        for row in existing_indep:
            sid   = row['slot_id']
            vtype = row['vehicle__vehicle_type'] or ''
            if vtype == 'car' and sid in car_remaining:
                car_remaining[sid] = max(0, car_remaining[sid] - 1)
            elif vtype in ('bike', 'scooter') and sid in tw_remaining:
                tw_remaining[sid]  = max(0, tw_remaining[sid] - 1)

        # ── Deduct pending / confirmed / completed PublicBookings ── #
        # PublicBooking stores vehicle_type directly on the row.
        public_bookings = (
            PublicBooking.objects
            .filter(date=target_date, status__in=('pending', 'confirmed', 'completed'))
            .values('slot_id', 'vehicle_type')
        )
        for row in public_bookings:
            sid   = row['slot_id']
            vtype = row['vehicle_type'] or ''
            if vtype == 'car' and sid in car_remaining:
                car_remaining[sid] = max(0, car_remaining[sid] - 1)
            elif vtype in ('bike', 'scooter') and sid in tw_remaining:
                tw_remaining[sid]  = max(0, tw_remaining[sid] - 1)

        # ── Build slot list for this day ── #
        # A slot is shown if the institute physically has the infrastructure
        # to run it (tracks, vehicles, instructors exist).
        # We do NOT hide slots just because they are fully booked — the
        # template shows available chip(s) or "Fully Booked" accordingly.
        open_slots = []
        for s in slots:
            car_left = car_remaining.get(s.id, 0)
            tw_left  = tw_remaining.get(s.id, 0)

            # Hide only if there is literally no physical capacity for either
            # category — i.e. the institute has no usable tracks/vehicles at all.
            if car_base <= 0 and tw_base <= 0:
                continue

            # Respect the booking cutoff window.
            # A negative hours_until means the slot has already passed today.
            slot_start  = datetime.combine(target_date, s.start_time)
            hours_until = (slot_start - now).total_seconds() / 3600
            if hours_until < config.public_booking_cutoff_hours:
                continue

            open_slots.append({
                'label':      s.label,
                'start_time': s.start_time,
                'end_time':   s.end_time,
                'four_wheel': max(0, car_left),
                'two_wheel':  max(0, tw_left),
            })

        # Always include the day as long as it has slots within the cutoff window.
        if open_slots:
            result.append({
                'date':         target_date,
                'date_display': target_date.strftime('%a, %d %b'),
                'is_today':     target_date == today,
                'slots':        open_slots,
            })

    return result


# ---------------------------------------------------------------------------
# PUBLIC LANDING PAGE
# ---------------------------------------------------------------------------

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

    # Load config once and pass it through so _build_public_vacancy doesn't
    # make a second DB round-trip.
    config           = SchedulingConfig.load()
    working_days     = _get_working_days_ahead(5)
    vacant_slot_days = _build_public_vacancy(working_days, config=config)

    return render(request, 'index.html', {
        'courses':          courses,
        'instructors':      instructors,
        'vehicles':         vehicles,
        'vacant_slot_days': vacant_slot_days,
        'session_fee':      config.public_session_fee,
        'booking_enabled':  config.public_booking_enabled,
    })


# ---------------------------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------------------------

@login_required
@role_required(['admin'])
def admin_dashboard(request):
    from django.db.models import Sum, Value, CharField
    from django.db.models.functions import TruncMonth
    import json
    import decimal

    class DecimalEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, decimal.Decimal):
                return float(obj)
            return super().default(obj)

    today = date.today()
    current_month_start = today.replace(day=1)

    # ── Existing user/session stats ──────────────────────────────────────────
    total_users       = User.objects.count()
    total_instructors = Instructor.objects.count()
    total_trainees    = Trainee.objects.count()
    active_trainees   = Trainee.objects.filter(
        status__in=['ENROLLED', 'TRAINING']
    ).count()
    recent_users = User.objects.order_by('-id')[:5]

    config = SchedulingConfig.load()
    pending_sessions_count = Session.objects.filter(status='pending').count()
    todays_sessions_count  = Session.objects.filter(
        date=today
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

    pending_public_bookings = PublicBooking.objects.filter(status='pending').count()
    public_debt_qs    = PublicBooking.objects.filter(
        fee_paid=False, status__in=('confirmed', 'completed'),
    )
    public_debt_count = public_debt_qs.count()

    # ── Financial: Income ────────────────────────────────────────────────────
    payment_sum         = Payment.objects.aggregate(t=Sum('amount'))['t'] or 0
    session_payment_sum = SessionPayment.objects.aggregate(t=Sum('amount'))['t'] or 0
    total_income        = payment_sum + session_payment_sum

    monthly_payment_sum         = Payment.objects.filter(
        date__gte=current_month_start
    ).aggregate(t=Sum('amount'))['t'] or 0
    monthly_session_payment_sum = SessionPayment.objects.filter(
        date__gte=current_month_start
    ).aggregate(t=Sum('amount'))['t'] or 0
    monthly_income = monthly_payment_sum + monthly_session_payment_sum

    # ── Financial: Expenses ──────────────────────────────────────────────────
    total_expenses   = Expense.objects.aggregate(t=Sum('amount'))['t'] or 0
    monthly_expenses = Expense.objects.filter(
        date__gte=current_month_start
    ).aggregate(t=Sum('amount'))['t'] or 0

    # ── Financial: Outstanding dues ──────────────────────────────────────────
    unpaid_fee_records = FeeRecord.objects.filter(
        status__in=('unpaid', 'partial')
    )
    pending_dues = sum(r.remaining() for r in unpaid_fee_records)

    public_debt_total = PublicBooking.objects.filter(
        fee_paid=False, status__in=('confirmed', 'completed'),
    ).aggregate(t=Sum('fee_amount'))['t'] or 0

    # ── Financial: P&L ───────────────────────────────────────────────────────
    profit_loss = monthly_income - monthly_expenses

    # ── Financial: 6-month income trend ─────────────────────────────────────
    six_months_ago = (today.replace(day=1).replace(month=today.month - 5)
                      if today.month > 5
                      else today.replace(year=today.year - 1,
                                         month=today.month + 7, day=1))

    def build_monthly_series(queryset, date_field, amount_field='amount'):
        """Annotate a queryset by month and return last-6-months dict keyed by 'YYYY-MM'."""
        qs = (queryset.objects.all() if isinstance(queryset, type) else queryset)
        return {
            entry['month'].strftime('%Y-%m'): float(entry['total'])
            for entry in qs.filter(
                **{f'{date_field}__gte': six_months_ago}
            ).annotate(
                month=TruncMonth(date_field)
            ).values('month').annotate(total=Sum(amount_field)).order_by('month')
        }

    # Build a canonical list of the last 6 month labels
    month_labels = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_labels.append(date(y, m, 1).strftime('%Y-%m'))

    pay_by_month  = build_monthly_series(Payment.objects.all(),        'date')
    sess_by_month = build_monthly_series(SessionPayment.objects.all(), 'date')
    exp_by_month  = build_monthly_series(Expense.objects.all(),        'date')

    income_by_month  = [
        {'month': m, 'income': (pay_by_month.get(m, 0) + sess_by_month.get(m, 0))}
        for m in month_labels
    ]
    expense_by_month = [
        {'month': m, 'expense': exp_by_month.get(m, 0)}
        for m in month_labels
    ]

    # ── Financial: Expense breakdown by category ─────────────────────────────
    expense_by_category = [
        {'category': row['category'], 'total': float(row['total'])}
        for row in Expense.objects.values('category')
                                  .annotate(total=Sum('amount'))
                                  .order_by('-total')
    ]

    # ── Financial: Recent payments (course + session, last 10 combined) ──────
    course_payments = list(
        Payment.objects.select_related('fee_record', 'fee_record__trainee',
                                       'fee_record__trainee__user')
                       .order_by('-date')
                       .values('id', 'amount', 'method', 'date',
                               label=Value('course', output_field=CharField()))
    )[:10]
    session_payments = list(
        SessionPayment.objects.select_related('session')
                              .order_by('-date')
                              .values('id', 'amount', 'method', 'date',
                                      label=Value('session', output_field=CharField()))
    )[:10]

    # Normalise to a common key 'date' for sorting
    for p in course_payments:
        p['date'] = p.pop('date')

    recent_payments = sorted(
        course_payments + session_payments,
        key=lambda x: x['date'],
        reverse=True,
    )[:10]

    # ── Financial: Payment method breakdown ──────────────────────────────────
    course_by_method = {
        row['method']: float(row['total'])
        for row in Payment.objects.values('method').annotate(total=Sum('amount'))
    }
    session_by_method = {
        row['method']: float(row['total'])
        for row in SessionPayment.objects.values('method').annotate(total=Sum('amount'))
    }
    all_methods = set(course_by_method) | set(session_by_method)
    payment_method_breakdown = [
        {
            'method': m,
            'total':  course_by_method.get(m, 0) + session_by_method.get(m, 0),
        }
        for m in sorted(all_methods)
    ]

    return render(request, 'admin_dashboard.html', {
        # ── Users & scheduling ───────────────────────────────────────────────
        'total_users':               total_users,
        'total_instructors':         total_instructors,
        'total_trainees':            total_trainees,
        'active_trainees':           active_trainees,
        'recent_users':              recent_users,
        'pending_sessions_count':    pending_sessions_count,
        'todays_sessions_count':     todays_sessions_count,
        'reschedule_queue_count':    reschedule_queue_count,
        'flagged_count':             flagged_count,
        'reschedule_requests_count': reschedule_requests_count,
        'pending_public_bookings':   pending_public_bookings,
        'public_debt_count':         public_debt_count,
        # ── Financial ────────────────────────────────────────────────────────
        'total_income':              total_income,
        'monthly_income':            monthly_income,
        'total_expenses':            total_expenses,
        'monthly_expenses':          monthly_expenses,
        'pending_dues':              pending_dues,
        'public_debt_total':         public_debt_total,
        'profit_loss':               profit_loss,
        'income_by_month':           json.dumps(income_by_month,          cls=DecimalEncoder),
        'expense_by_month':          json.dumps(expense_by_month,         cls=DecimalEncoder),
        'expense_by_category':       json.dumps(expense_by_category,      cls=DecimalEncoder),
        'recent_payments':           recent_payments,
        'payment_method_breakdown':  json.dumps(payment_method_breakdown, cls=DecimalEncoder),
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


# ---------------------------------------------------------------------------
# SUPERVISOR DASHBOARD
# ---------------------------------------------------------------------------

@login_required
@role_required(['supervisor'])
def supervisor_dashboard(request):
    today = date.today()
    one_week_ago  = today - timedelta(days=7)
    thirty_days_ago = today - timedelta(days=30)
 
    # ------------------------------------------------------------------ #
    #  Existing stats                                                       #
    # ------------------------------------------------------------------ #
    total_trainees  = Trainee.objects.count()
    active_trainees = Trainee.objects.filter(status__in=['ENROLLED', 'TRAINING']).count()
 
    todays_sessions = (
        Session.objects
        .filter(date=today)
        .exclude(status='cancelled')
        .select_related('trainee__user', 'instructor__user', 'slot', 'vehicle', 'track')
        .order_by('slot__slot_number')
    )
    sessions_today           = todays_sessions.count()
    sessions_completed_today = todays_sessions.filter(status='completed').count()
    sessions_remaining_today = todays_sessions.exclude(status='completed').count()
 
    pending_count = Session.objects.filter(status='pending').count()
 
    config = SchedulingConfig.load()
    reschedule_queue_count = RescheduleQueue.objects.filter(
        resolved=False,
        attempt_count__lt=config.max_reschedule_attempts,
    ).count()
 
    month_start    = today.replace(day=1)
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
 
    total_vehicles   = Vehicle.objects.count()
    vehicles_on_duty = Vehicle.objects.filter(status='in_use').count()
    reschedule_requests_count = RescheduleRequest.objects.filter(
        status='pending'
    ).count()
 
    pending_public_bookings = PublicBooking.objects.filter(status='pending').count()
    public_debt_count = PublicBooking.objects.filter(
        fee_paid=False, status__in=('confirmed', 'completed'),
    ).count()
 
    # ------------------------------------------------------------------ #
    #  ALERTS — Overdue Payments                                           #
    # ------------------------------------------------------------------ #
 
    # Trainees with an unpaid FeeRecord created 30+ days ago
    overdue_trainee_ids = (
        FeeRecord.objects
        .filter(status='unpaid', created_at__date__lt=thirty_days_ago)
        .values_list('trainee_id', flat=True)
        .distinct()
    )
    overdue_trainees = (
        Trainee.objects
        .filter(id__in=overdue_trainee_ids)
        .select_related('user')
    )
 
    # Walk-in (PublicBooking) debts older than 30 days.
    # No select_related here — PublicBooking stores guest details as plain
    # fields (full_name / phone / email) rather than a User FK.
    overdue_walkins = PublicBooking.objects.filter(
        fee_paid=False, created_at__date__lt=thirty_days_ago
    )
 
    # ------------------------------------------------------------------ #
    #  ALERTS — Insufficient Practice                                      #
    # ------------------------------------------------------------------ #
 
    # Active trainees whose completed-session count is below the expected
    # rate derived from (course.total_lessons / course.duration_days) *
    # days elapsed since enrollment.
    #
    # We annotate each active trainee with their completed session count,
    # then filter in Python because the expected count depends on per-row
    # enrollment dates and course rates that can't be expressed cleanly in
    # a single ORM annotation without a computed field or raw SQL.
 
    active_trainee_qs = (
        Trainee.objects
        .filter(status__in=['ENROLLED', 'TRAINING'])
        .select_related('user', 'course')
        .annotate(
            completed_sessions=Count(
                'sessions',
                filter=Q(sessions__status='completed'),
            )
        )
    )
 
    low_practice_trainees = []
    for trainee in active_trainee_qs:
        course = trainee.course
        if not course or not course.duration_days or not course.total_lessons:
            continue
        # Days since the trainee enrolled (floor at 0)
        days_enrolled = max((today - trainee.enrollment_date).days, 0)
        # Expected sessions completed by now at the course's lesson rate
        daily_rate = course.total_lessons / course.duration_days
        expected = daily_rate * days_enrolled
        if trainee.completed_sessions < expected:
            low_practice_trainees.append(trainee)
 
    # ------------------------------------------------------------------ #
    #  ALERTS — Underutilized Resources                                    #
    # ------------------------------------------------------------------ #
 
    # Vehicles available but unused in the last 7 days
    active_vehicle_ids_last_week = (
        Session.objects
        .filter(date__gte=one_week_ago, date__lte=today)
        .exclude(vehicle__isnull=True)
        .values_list('vehicle_id', flat=True)
        .distinct()
    )
    idle_vehicles = Vehicle.objects.filter(status='available').exclude(
        id__in=active_vehicle_ids_last_week
    )
 
    # Instructors with no sessions in the last 7 days
    active_instructor_ids_last_week = (
        Session.objects
        .filter(date__gte=one_week_ago, date__lte=today)
        .exclude(instructor__isnull=True)
        .values_list('instructor_id', flat=True)
        .distinct()
    )
    idle_instructors = (
        Instructor.objects
        .exclude(id__in=active_instructor_ids_last_week)
        .select_related('user')
    )
 
    # Active tracks with no sessions in the last 7 days
    active_track_ids_last_week = (
        Session.objects
        .filter(date__gte=one_week_ago, date__lte=today)
        .exclude(track__isnull=True)
        .values_list('track_id', flat=True)
        .distinct()
    )
    idle_tracks = Track.objects.filter(status='active').exclude(
        id__in=active_track_ids_last_week
    )
 
    # ------------------------------------------------------------------ #
    #  Render                                                              #
    # ------------------------------------------------------------------ #
    return render(request, 'supervisor_dashboard.html', {
        # --- existing ---
        'total_trainees':             total_trainees,
        'active_trainees':            active_trainees,
        'todays_sessions':            todays_sessions,
        'sessions_today':             sessions_today,
        'sessions_completed_today':   sessions_completed_today,
        'sessions_remaining_today':   sessions_remaining_today,
        'pending_count':              pending_count,
        'reschedule_queue_count':     reschedule_queue_count,
        'reschedule_requests_count':  reschedule_requests_count,
        'top_instructors':            instructors_qs,
        'total_vehicles':             total_vehicles,
        'vehicles_on_duty':           vehicles_on_duty,
        'pending_public_bookings':    pending_public_bookings,
        'public_debt_count':          public_debt_count,
        # --- alerts: overdue payments ---
        'overdue_trainees':           overdue_trainees,
        'overdue_walkins':            overdue_walkins,
        # --- alerts: insufficient practice ---
        'low_practice_trainees':      low_practice_trainees,
        # --- alerts: underutilized resources ---
        'idle_vehicles':              idle_vehicles,
        'idle_instructors':           idle_instructors,
        'idle_tracks':                idle_tracks,
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

    fee_record = getattr(trainee, 'fee_record', None)
    paid       = fee_record.total_paid()    if fee_record else 0
    remaining  = fee_record.remaining()     if fee_record else 0
    discount   = fee_record.discount_amount if fee_record else 0
    final_fee  = fee_record.final_fee()     if fee_record else 0

    upcoming_sessions = Session.objects.filter(
        trainee=trainee,
        date__gte=date.today(),
        date__lte=date.today() + timedelta(days=7),
    ).exclude(status='cancelled').select_related(
        'slot', 'vehicle', 'track', 'instructor'
    ).order_by('date', 'slot__slot_number')

    slot_preferences = TraineePreference.objects.filter(
        trainee=trainee,
    ).select_related('slot').order_by('priority')

    return render(request, 'trainee_dashboard.html', {
        'trainee':           trainee,
        'fee_record':        fee_record,
        'paid':              paid,
        'remaining':         remaining,
        'discount':          discount,
        'final_fee':         final_fee,
        'upcoming_sessions': upcoming_sessions,
        'slot_preferences':  slot_preferences,
    })