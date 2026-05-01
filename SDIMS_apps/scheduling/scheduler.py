"""
scheduling/scheduler.py

The core scheduling engine for SDIMS.

Entry point:  run_scheduler(target_date, triggered_by=None)

Called by:
  - Celery beat task (daily, automated)
  - Manual trigger view (POST /scheduling/run-scheduler/)

The entire run executes inside a single database transaction.
If anything fails mid-run, no sessions are created for that day.

"""

import logging
from collections import defaultdict
from datetime import date as date_type

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    DailyScheduleRun,
    RescheduleQueue,
    SchedulingConfig,
    Session,
    TimeSlot,
    Track,
)

logger = logging.getLogger(__name__)
User   = get_user_model()


# Public entry point

def run_scheduler(target_date: date_type, triggered_by=None) -> DailyScheduleRun:
    """
    Schedule sessions for target_date.

    Returns the DailyScheduleRun audit record (always, even on failure).
    Raises nothing — all errors are caught, logged, and written to run.notes.
    """
    run = DailyScheduleRun.objects.create(
        run_date     = target_date,
        triggered_by = triggered_by,
    )
    logger.info("Scheduler started for %s (run_id=%s)", target_date, run.pk)

    try:
        sessions, notes = _execute(target_date, run)
        run.sessions_created = len(sessions)
        run.notes            = "\n".join(notes)
        run.completed_at     = timezone.now()
        run.save(update_fields=['sessions_created', 'notes', 'completed_at'])
        logger.info(
            "Scheduler completed for %s — %d session(s) created.",
            target_date, len(sessions),
        )
    except Exception as exc:
        run.notes        = f"FATAL ERROR: {exc}"
        run.completed_at = timezone.now()
        run.save(update_fields=['notes', 'completed_at'])
        logger.exception("Scheduler fatal error for %s", target_date)

    return run


# Internal execution (wrapped in a transaction)

@transaction.atomic
def _execute(target_date: date_type, run: DailyScheduleRun):
    """
    Core logic. Runs atomically — if anything raises, the whole run
    is rolled back and no sessions are written.
    """
    from SDIMS_apps.trainees.models import Trainee
    from SDIMS_apps.instructors.models import Instructor
    from SDIMS_apps.vehicles.models import Vehicle

    config = SchedulingConfig.load()
    notes  = []
    slots  = list(TimeSlot.objects.order_by('slot_number'))

    
    # Step 1: Build capacity map for the day
    
    capacity_map = _build_capacity_map(target_date, slots, config)

    
    # Step 2: Identify available resources
    
    available_vehicles    = list(Vehicle.objects.filter(status='available'))
    available_instructors = list(
        Instructor.objects.filter(status='active')
    )
    available_tracks = list(Track.objects.filter(status='active'))

    if not available_vehicles:
        notes.append("WARNING: No active vehicles found. No sessions created.")
        return [], notes

    if not available_tracks:
        notes.append("WARNING: No active tracks found. No sessions created.")
        return [], notes

    
    # Step 3: Collect trainees to schedule — in priority order
    

    # Priority 1: Reschedule queue (unresolved, under attempt limit)
    reschedule_entries = list(
        RescheduleQueue.objects.filter(
            resolved=False,
            attempt_count__lt=config.max_reschedule_attempts,
        ).select_related('trainee', 'trainee__course')
        # ordering defined on Meta: priority ASC, priority_score DESC, etc.
    )

    # Priority 2: Course trainees (ENROLLED or TRAINING, not already scheduled today)
    already_scheduled_today = set(
        Session.objects.filter(date=target_date)
        .values_list('trainee_id', flat=True)
    )
    course_trainees = list(
        Trainee.objects.filter(
            status__in=('ENROLLED', 'TRAINING'),
        ).exclude(
            id__in=already_scheduled_today,
        ).select_related('course')
        .order_by('enrollment_date')
    )

    # Priority 3: Independent trainees (no course, not scheduled today)
    independent_trainees = list(
        Trainee.objects.filter(
            course__isnull=True,
            status='ENROLLED',
        ).exclude(
            id__in=already_scheduled_today,
        ).order_by('id')
    )

    
    # Step 4: Process each group — collect built sessions
    
    built_sessions  = []   # list of (Session instance, RescheduleQueue entry or None)

    # --- 4a. Reschedule queue ---
    for entry in reschedule_entries:
        trainee = entry.trainee
        # FIX [Bug 4]: compare trainee objects, not raw IDs
        if _trainee_at_daily_limit(trainee, target_date, built_sessions, config):
            continue

        trainee_type = 'course' if trainee.course_id else 'independent'
        slot = _find_slot(trainee, target_date, capacity_map, trainee_type)
        if not slot:
            entry.increment_attempt()
            notes.append(
                f"RESCHEDULE: No slot found for {trainee} "
                f"(attempt {entry.attempt_count}/{config.max_reschedule_attempts})."
            )
            continue

        session = _build_session(
            trainee        = trainee,
            slot           = slot,
            target_date    = target_date,
            capacity_map   = capacity_map,
            vehicles       = available_vehicles,
            instructors    = available_instructors,
            tracks         = available_tracks,
            trainee_type   = trainee_type,
            run            = run,
            notes          = notes,
        )
        if session:
            built_sessions.append((session, entry))
        else:
            entry.increment_attempt()
            notes.append(
                f"RESCHEDULE: Resources unavailable for {trainee} in {slot}."
            )

    # --- 4b. Course trainees ---
    for trainee in course_trainees:
        if _trainee_at_daily_limit(trainee, target_date, built_sessions, config):
            continue

        slot = _find_slot(trainee, target_date, capacity_map, trainee_type='course')
        if not slot:
            notes.append(f"SKIP (course): No available slot for {trainee}.")
            continue

        session = _build_session(
            trainee      = trainee,
            slot         = slot,
            target_date  = target_date,
            capacity_map = capacity_map,
            vehicles     = available_vehicles,
            instructors  = available_instructors,
            tracks       = available_tracks,
            trainee_type = 'course',
            run          = run,
            notes        = notes,
        )
        if session:
            built_sessions.append((session, None))

    # --- 4c. Independent trainees ---
    for trainee in independent_trainees:
        if _trainee_at_daily_limit(trainee, target_date, built_sessions, config):
            continue

        slot = _find_slot(trainee, target_date, capacity_map, trainee_type='independent')
        if not slot:
            notes.append(f"SKIP (independent): No available slot for {trainee}.")
            continue

        session = _build_session(
            trainee      = trainee,
            slot         = slot,
            target_date  = target_date,
            capacity_map = capacity_map,
            vehicles     = available_vehicles,
            instructors  = available_instructors,
            tracks       = available_tracks,
            trainee_type = 'independent',
            run          = run,
            notes        = notes,
        )
        if session:
            built_sessions.append((session, None))

    
    # Step 5: FIX [Bug 1] — Save each session individually so that
    #         Session.clean() (full_clean) is always called.
    #         bulk_create skips clean() entirely, which bypassed all
    #         model-level validation (track capacity, daily limits, etc.)
    
    saved_sessions = []
    for session, reschedule_entry in built_sessions:
        try:
            session.full_clean()   # runs Session.clean() + field validation
            session.save()
            saved_sessions.append(session)

            # Resolve the reschedule queue entry now that we have a real PK
            if reschedule_entry is not None:
                reschedule_entry.resolve(session)

        except ValidationError as exc:
            notes.append(
                f"VALIDATION ERROR saving session for {session.trainee} "
                f"in {session.slot} on {target_date}: {exc.message_dict if hasattr(exc, 'message_dict') else exc.messages}"
            )
            logger.warning(
                "Session validation failed for trainee=%s slot=%s date=%s: %s",
                session.trainee, session.slot, target_date, exc,
            )
        except Exception as exc:
            notes.append(
                f"ERROR saving session for {session.trainee} "
                f"in {session.slot} on {target_date}: {exc}"
            )
            logger.exception(
                "Unexpected error saving session for trainee=%s slot=%s",
                session.trainee, session.slot,
            )

    return saved_sessions, notes


# Capacity map

def _build_capacity_map(target_date, slots, config):
    """
    Build an in-memory dict tracking remaining capacity per slot.
    Accounts for sessions already existing for target_date (e.g. from a
    previous partial run or manually created sessions).

    FIX [Bug 5]: Independent capacity now uses unguided_total (track + vehicle
    only) instead of guided_total so that instructor shortages don't
    incorrectly cap independent trainee slots.

    Structure per slot_id:
    {
        'course_remaining':       int,
        'independent_remaining':  int,
        'booked_vehicle_ids':     set,
        'booked_instructor_ids':  set,
        'track_usage':            {track_id: count},   # max 2 per track
    }
    """
    from SDIMS_apps.vehicles.models import Vehicle
    from SDIMS_apps.instructors.models import Instructor

    tracks = list(Track.objects.filter(status='active'))

    active_vehicles     = Vehicle.objects.filter(status='available').count()
    active_instructors = Instructor.objects.filter(status='active').count()
    active_tracks = len(tracks)

    track_capacity      = active_tracks * 2        # 2 vehicles per track
    vehicle_capacity    = active_vehicles
    instructor_capacity = active_instructors

    # Guided sessions need track + vehicle + instructor
    guided_total   = min(track_capacity, vehicle_capacity, instructor_capacity)

    # FIX [Bug 5]: Unguided/independent sessions only need track + vehicle
    unguided_total = min(track_capacity, vehicle_capacity)

    # Course slots reserved from guided capacity
    course_reserved = max(1, round(guided_total * config.course_capacity_pct))
    # Independent slots come from unguided capacity, minus what course already uses
    # (course trainees also occupy tracks/vehicles even though they're guided)
    independent_reserved = max(0, unguided_total - course_reserved)

    capacity_map = {}
    for slot in slots:
        capacity_map[slot.id] = {
            'slot':                   slot,
            'course_remaining':       course_reserved,
            'independent_remaining':  independent_reserved,
            'booked_vehicle_ids':     set(),
            'booked_instructor_ids':  set(),
            'track_usage':            defaultdict(int),
        }

    # Deduct already-existing sessions for this date
    existing = Session.objects.filter(
        date=target_date
    ).exclude(
        status='cancelled'
    ).values('slot_id', 'vehicle_id', 'instructor_id', 'track_id', 'trainee_type')

    for s in existing:
        sid = s['slot_id']
        if sid not in capacity_map:
            continue
        cap = capacity_map[sid]
        if s['vehicle_id']:
            cap['booked_vehicle_ids'].add(s['vehicle_id'])
        if s['instructor_id']:
            cap['booked_instructor_ids'].add(s['instructor_id'])
        if s['track_id']:
            cap['track_usage'][s['track_id']] += 1
        if s['trainee_type'] == 'course':
            cap['course_remaining']      = max(0, cap['course_remaining'] - 1)
        else:
            cap['independent_remaining'] = max(0, cap['independent_remaining'] - 1)

    return capacity_map


# Slot finder — preferred slots first, then nearest-available fallback

def _find_slot(trainee, target_date, capacity_map, trainee_type):
    """
    Try the trainee's preferred slots in priority order.
    If all are full, expand outward from the top preference:
        earlier → later → earlier → later …

    Returns a TimeSlot instance or None.
    """
    preferences = list(
        trainee.slot_preferences.select_related('slot').order_by('priority')
    )

    # Try preferred slots first
    for pref in preferences:
        if _slot_has_capacity(pref.slot, capacity_map, trainee_type):
            return pref.slot

    # No preferred slot available — expand outward from top preference
    if not preferences:
        # Trainee has no preferences — try all slots in order
        for slot in TimeSlot.objects.order_by('slot_number'):
            if _slot_has_capacity(slot, capacity_map, trainee_type):
                return slot
        return None

    base_num  = preferences[0].slot.slot_number
    all_slots = {s.slot_number: s for s in TimeSlot.objects.all()}

    low  = base_num - 1
    high = base_num + 1

    while low >= 1 or high <= 6:
        if low >= 1:
            candidate = all_slots.get(low)
            if candidate and _slot_has_capacity(candidate, capacity_map, trainee_type):
                return candidate
        if high <= 6:
            candidate = all_slots.get(high)
            if candidate and _slot_has_capacity(candidate, capacity_map, trainee_type):
                return candidate
        low  -= 1
        high += 1

    return None


def _slot_has_capacity(slot, capacity_map, trainee_type):
    """Return True if the slot still has remaining capacity for trainee_type."""
    cap = capacity_map.get(slot.id)
    if not cap:
        return False
    if trainee_type == 'course':
        return cap['course_remaining'] > 0
    return cap['independent_remaining'] > 0


# Resource assignment — builds an unsaved Session

def _build_session(
    trainee, slot, target_date, capacity_map,
    vehicles, instructors, tracks,
    trainee_type, run, notes,
):
    """
    Given a confirmed slot, pick an available vehicle, track, and
    (if guided) instructor. Returns an unsaved Session or None.

    Renamed from _assign_resources to make it clear this does NOT save.
    Saving (with full_clean) now happens in _execute Step 5.
    """
    cap = capacity_map[slot.id]

    session_type = _determine_session_type(trainee)

    # Pick vehicle (matching course vehicle type if applicable)
    required_vehicle_type = (
        trainee.course.vehicle_type
        if (hasattr(trainee, 'course') and trainee.course)
        else None
    )
    vehicle = _pick_vehicle(vehicles, cap, required_vehicle_type)
    if not vehicle:
        notes.append(
            f"SKIP: No available vehicle for {trainee} in {slot} "
            f"(type={required_vehicle_type})."
        )
        return None

    # Pick track (least loaded that has room)
    track = _pick_track(tracks, cap)
    if not track:
        notes.append(f"SKIP: No available track for {trainee} in {slot}.")
        return None

    # Pick instructor (guided only)
    instructor = None
    if session_type == 'guided':
        instructor = _pick_instructor(instructors, cap)
        if not instructor:
            notes.append(
                f"SKIP: No available instructor for guided session "
                f"({trainee}) in {slot}."
            )
            return None

    # Pick supervisor
    supervisor = _get_default_supervisor()
    if not supervisor:
        notes.append(f"SKIP: No supervisor available for {trainee} in {slot}.")
        return None

    # Update capacity map (in-memory) so subsequent trainees see correct state
    cap['booked_vehicle_ids'].add(vehicle.id)
    cap['track_usage'][track.id] += 1
    if instructor:
        cap['booked_instructor_ids'].add(instructor.id)
    if trainee_type == 'course':
        cap['course_remaining']      -= 1
    else:
        cap['independent_remaining'] -= 1

    # Return unsaved Session — full_clean + save happens in _execute
    return Session(
        trainee      = trainee,
        slot         = slot,
        date         = target_date,
        vehicle      = vehicle,
        track        = track,
        instructor   = instructor,
        supervisor   = supervisor,
        session_type = session_type,
        trainee_type = trainee_type,
        status       = 'pending',
        schedule_run = run,
    )


# Helper pickers

def _determine_session_type(trainee):
    """
    Guided  → beginner or intermediate course level.
    Unguided → advanced course level or independent (no course).
    """
    if hasattr(trainee, 'course') and trainee.course:
        if trainee.course.level in ('Beginner', 'Intermediate'):
            return 'guided'
        return 'unguided'
    return 'unguided'


def _pick_vehicle(vehicles, cap, required_type=None):
    """Return the first available vehicle not already booked in this slot."""
    for v in vehicles:
        if v.id in cap['booked_vehicle_ids']:
            continue
        if required_type and v.vehicle_type != required_type:
            continue
        return v
    return None


def _pick_track(tracks, cap):
    """
    Return the active track with the least current usage that still has
    room (track capacity = 2 vehicles per slot).
    """
    available = [t for t in tracks if cap['track_usage'][t.id] < 2]
    if not available:
        return None
    return min(available, key=lambda t: cap['track_usage'][t.id])


def _pick_instructor(instructors, cap):
    """Return the first available instructor not already booked in this slot."""
    for i in instructors:
        if i.id not in cap['booked_instructor_ids']:
            return i
    return None


def _get_default_supervisor():
    """
    Fetch a fallback supervisor. Replace with a smarter strategy
    (e.g. on-duty roster, round-robin) when that feature is built.
    """
    return (
        User.objects.filter(role='supervisor', is_active=True)
        .order_by('id')
        .first()
    )


# Daily limit guard

def _trainee_at_daily_limit(trainee, target_date, built_sessions, config):
    """
    Check if trainee has already hit their daily session cap,
    counting both DB-persisted sessions and sessions queued in this run.

    FIX [Bug 4]: Compare trainee objects directly instead of raw .id
    to avoid false mismatches on unsaved objects whose trainee_id may
    not yet be populated.
    """
    db_count = Session.objects.filter(
        trainee=trainee,
        date=target_date,
    ).exclude(status='cancelled').count()

    # built_sessions is now list of (Session, entry_or_None) tuples
    run_count = sum(
        1 for s, _ in built_sessions
        if s.trainee == trainee
    )

    return (db_count + run_count) >= config.max_sessions_per_trainee_per_day