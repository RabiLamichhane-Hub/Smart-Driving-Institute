from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


# 1. Track

class Track(models.Model):
    """
    Physical driving track on the premises.

    Track types:
        - 'car'        : Only used for Car courses/vehicles.
        - 'two_wheeler': Used for Bike and Scooter courses/vehicles.

    Rule: 1 track handles at most 2 vehicles simultaneously per slot.
    This is enforced in Session.clean() — not here — because it depends
    on cross-row aggregate logic.

    Track ↔ vehicle compatibility is also enforced in Session.clean()
    by calling Track.is_compatible_with(vehicle_type).
    """

    TRACK_TYPE_CHOICES = [
        ('car',          'Car Track'),
        ('two_wheeler',  'Two-Wheeler Track (Bike & Scooter)'),
    ]

    STATUS_CHOICES = [
        ('active',       'Active'),
        ('inactive',     'Inactive'),
        ('maintenance',  'Under Maintenance'),
    ]

    # Single source of truth: maps Vehicle.vehicle_type → required track_type.
    # Update this dict if new vehicle types are ever added to the system.
    TRACK_COMPATIBILITY = {
        'car':     'car',
        'bike':    'two_wheeler',
        'scooter': 'two_wheeler',
    }

    name       = models.CharField(max_length=50, unique=True)
    track_type = models.CharField(
        max_length=20,
        choices=TRACK_TYPE_CHOICES,
        help_text="Determines which vehicle types are permitted on this track.",
    )
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes      = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_track_type_display()})"

    def is_compatible_with(self, vehicle_type: str) -> bool:
        """
        Returns True if this track may be used for the given vehicle_type.
        Accepts both lowercase ('car', 'bike', 'scooter') and title-case
        ('Car', 'Bike', 'Scooter') — the value is normalised internally.
        Unknown vehicle types always return False.

        FIX Bug 4: added .lower() so callers using title-case strings (e.g.
        from Vehicle.get_vehicle_type_display()) no longer silently return
        False and block track assignment.
        """
        return self.TRACK_COMPATIBILITY.get(vehicle_type.lower()) == self.track_type


# 2. TimeSlot  (seeded once — never created via UI)

class TimeSlot(models.Model):
    """
    Fixed, non-overlapping 1-hour slots shared across all days.
    Populated via: python manage.py seed_slots
    Slot numbers: 1=08:00, 2=09:00, 3=10:00, 4=11:00, 5=12:00, 6=13:00, [break 14:00], 7=15:00, 8=16:00
    """

    slot_number = models.PositiveSmallIntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
    )
    label      = models.CharField(max_length=30)
    start_time = models.TimeField()
    end_time   = models.TimeField()

    class Meta:
        ordering = ['slot_number']

    def __str__(self):
        return self.label

    def clean(self):
        if self.start_time and self.end_time:
            from datetime import datetime
            start_dt = datetime.combine(datetime.today(), self.start_time)
            end_dt   = datetime.combine(datetime.today(), self.end_time)
            if (end_dt - start_dt).seconds != 3600:
                raise ValidationError("Each slot must be exactly 1 hour.")


# 3. SchedulingConfig  (singleton — edited only via Django admin)

class SchedulingConfig(models.Model):
    """
    Admin-tunable parameters consumed by the scheduler and model validation.
    Singleton: only one row (pk=1) should ever exist — use SchedulingConfig.load().
    """

    course_capacity_pct = models.FloatField(
        default=0.70,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Fraction of each slot's capacity reserved for course trainees (0.0–1.0).",
    )
    max_sessions_per_trainee_per_day = models.PositiveSmallIntegerField(
        default=1,
        help_text=(
            "Hard cap on how many sessions a single trainee can be "
            "scheduled for in one day. Enforced in Session.clean()."
        ),
    )
    max_reschedule_attempts = models.PositiveSmallIntegerField(
        default=3,
        help_text="Maximum scheduler attempts to re-place an absent trainee.",
    )
    schedule_days_ahead = models.PositiveSmallIntegerField(
        default=1,
        help_text="How many calendar days ahead each daily run targets.",
    )

    # --- Public / pay-per-session booking controls ---
    public_session_fee = models.DecimalField(
        max_digits=8, decimal_places=2,
        default=500.00,
        help_text="Fee charged per public/pay-per-session booking (Rs.).",
    )
    public_booking_enabled = models.BooleanField(
        default=True,
        help_text="Master switch to enable/disable public slot bookings.",
    )
    public_booking_cutoff_hours = models.PositiveSmallIntegerField(
        default=24,
        help_text="How many hours before a slot's start time public bookings close.",
    )

    class Meta:
        verbose_name        = "Scheduling Config"
        verbose_name_plural = "Scheduling Config"

    def __str__(self):
        return "Scheduling Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
    

# 3b.  HolidayOrDayOff  (custom day-off calendar)
class HolidayOrDayOff(models.Model):
    """
    A single date that is declared as a non-working day.
    Rules:
      - Saturdays (weekday 5) and Sundays (weekday 6) are ALWAYS off,
        enforced in Session.clean() and scheduler.is_working_day().
        They do NOT need an entry here.
      - This table is for extra off-days: public holidays, institute
        closures, special events, etc.
      - Created by admin or supervisor via the UI.
      - The scheduler and Session.clean() both consult is_working_day().
    """
    date        = models.DateField(unique=True, help_text="The date that is off.")
    reason      = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional: e.g. 'Dashain', 'Institute Annual Day', etc.",
    )
    declared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='declared_days_off',
    )
    declared_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering            = ['date']
        verbose_name        = "Holiday / Day Off"
        verbose_name_plural = "Holidays / Days Off"
    def __str__(self):
        label = self.reason or "Day Off"
        return f"{self.date} — {label}"
    def clean(self):
        super().clean()
        if self.date:
            # Prevent redundant entries for weekends (they're already always off)
            if self.date.weekday() in (5, 6):
                day_name = "Saturday" if self.date.weekday() == 5 else "Sunday"
                raise ValidationError(
                    f"{self.date} is a {day_name}. Weekends are always off — "
                    "no need to add a separate entry."
                )


# 4. TraineePreference

class TraineePreference(models.Model):
    """
    A trainee's ranked slot choices. One row per slot; priority=1 = top choice.
    Cleared and re-saved each time the trainee updates their preferences.
    """

    trainee  = models.ForeignKey(
        'trainees.Trainee',
        on_delete=models.CASCADE,
        related_name='slot_preferences',
    )
    slot     = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name='trainee_preferences',
    )
    priority = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        help_text="1 = top choice, 8 = last resort.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['trainee', 'priority']
        constraints = [
            models.UniqueConstraint(
                fields=['trainee', 'slot'],
                name='unique_trainee_slot_preference',
            ),
            models.UniqueConstraint(
                fields=['trainee', 'priority'],
                name='unique_trainee_priority',
            ),
        ]

    def __str__(self):
        return f"{self.trainee} — {self.slot} (priority {self.priority})"


# 5. DailyScheduleRun

class DailyScheduleRun(models.Model):
    """
    Audit record for every execution of the scheduling engine.
    Created at the start of each run; updated when the run completes.
    """

    run_date         = models.DateField(help_text="The date being scheduled for.")
    triggered_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='schedule_runs',
        help_text="Null = automated cron job.",
    )
    ran_at           = models.DateTimeField(auto_now_add=True)
    completed_at     = models.DateTimeField(null=True, blank=True)
    sessions_created = models.PositiveIntegerField(default=0)
    notes            = models.TextField(
        blank=True,
        help_text="Warnings, skipped trainees, resource shortfalls, etc.",
    )

    class Meta:
        ordering = ['-ran_at']

    def __str__(self):
        trigger = self.triggered_by or "cron"
        return f"Run for {self.run_date} (by {trigger}) — {self.sessions_created} sessions"


# 6. Session  (core scheduling model)

class Session(models.Model):
    """
    One training session = one trainee allocated to one slot on one day,
    with a vehicle, track, supervisor, and optionally an instructor.

    Validation in clean() enforces:
      [Issue 1]  Track capacity:       max 2 vehicles per track per slot
      [Issue 2]  Trainee daily limit:  from SchedulingConfig
      [Issue 6]  session_type ↔ instructor consistency (both directions)
      [Issue 7]  supervisor must always be set
      [Issue 8]  trainee_type must match trainee's actual enrollment state

    FIX [Bug 3]: trainee_type check now uses course_id (the raw FK integer)
    instead of accessing the related object via trainee.course. This avoids
    false mismatches when the related Course object exists in the DB but
    is temporarily not accessible (e.g. deferred queryset, deleted object
    still referenced by FK). Using the FK column is always reliable.
    """

    STATUS_CHOICES = [
        ('pending',   'Pending Approval'),
        ('scheduled', 'Scheduled'),
        ('ongoing',   'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    SESSION_TYPE_CHOICES = [
        ('guided',   'Guided (instructor present)'),
        ('unguided', 'Unguided (supervisor supervised)'),
    ]

    TRAINEE_TYPE_CHOICES = [
        ('course',      'Course Trainee'),
        ('independent', 'Independent Trainee'),
    ]

    # --- Core allocation fields -------------------------------------------

    trainee    = models.ForeignKey(
        'trainees.Trainee',
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    slot       = models.ForeignKey(
        TimeSlot,
        on_delete=models.PROTECT,
        related_name='sessions',
    )
    date       = models.DateField()
    vehicle    = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.PROTECT,
        related_name='sessions',
    )
    track      = models.ForeignKey(
        Track,
        on_delete=models.PROTECT,
        related_name='sessions',
    )

    instructor = models.ForeignKey(
        'instructors.Instructor',
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='sessions',
        help_text="Required for guided sessions; must be null for unguided.",
    )

    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='supervised_sessions',
        help_text=(
            "The supervisor accountable for this session. "
            "An instructor temporarily acting as supervisor also fills this field."
        ),
    )

    # --- Categorisation ---------------------------------------------------

    session_type = models.CharField(max_length=10, choices=SESSION_TYPE_CHOICES)

    trainee_type = models.CharField(max_length=12, choices=TRAINEE_TYPE_CHOICES)

    status       = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='pending',
    )

    # --- Booking source ---------------------------------------------------

    BOOKING_SOURCE_CHOICES = [
        ('scheduler', 'Auto-Scheduler'),
        ('manual',    'Manual (Admin/Supervisor)'),
    ]

    booking_source = models.CharField(
        max_length=10,
        choices=BOOKING_SOURCE_CHOICES,
        default='scheduler',
        help_text="How this session was created.",
    )

    # --- Audit / linkage --------------------------------------------------

    schedule_run = models.ForeignKey(
        DailyScheduleRun,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='sessions',
    )
    approved_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_sessions',
    )
    approved_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    # -----------------------------------------------------------------------
    # DB-level uniqueness constraints
    # -----------------------------------------------------------------------

    class Meta:
        ordering = ['date', 'slot__slot_number']
        constraints = [
            models.UniqueConstraint(
                fields=['slot', 'date', 'vehicle'],
                name='unique_vehicle_per_slot_day',
            ),
            models.UniqueConstraint(
                fields=['slot', 'date', 'instructor'],
                condition=models.Q(instructor__isnull=False),
                name='unique_instructor_per_slot_day',
            ),
            models.UniqueConstraint(
                fields=['slot', 'date', 'trainee'],
                name='unique_trainee_per_slot_day',
            ),
        ]

    def __str__(self):
        return (
            f"{self.trainee} | {self.slot} | {self.date} "
            f"[{self.get_status_display()}]"
        )

    # -----------------------------------------------------------------------
    # Model-level validation
    # -----------------------------------------------------------------------

    def clean(self):
        super().clean()

        # --- [Issue 9] Prevent sessions on weekends or declared day-off days ----
        if self.date:
            from .scheduler import is_working_day
            if not is_working_day(self.date):
                day_name = self.date.strftime('%A')
                raise ValidationError(
                    f"{self.date} ({day_name}) is a non-working day. "
                    "Sessions cannot be scheduled on weekends or declared holidays."
                )


        # --- [Track compatibility] Vehicle type must match track type --------
        if self.track_id and self.vehicle_id:
            try:
                from SDIMS_apps.vehicles.models import Vehicle as VehicleModel
                vehicle_type = VehicleModel.objects.filter(
                    pk=self.vehicle_id
                ).values_list('vehicle_type', flat=True).first()

                if vehicle_type and not self.track.is_compatible_with(vehicle_type):
                    raise ValidationError({
                        'track': (
                            f"Track '{self.track.name}' is a "
                            f"{self.track.get_track_type_display()} and cannot be used "
                            f"for a {vehicle_type} vehicle. "
                            "Please select a compatible track."
                        )
                    })
            except ValidationError:
                raise
            except Exception:
                # Relation not yet resolvable during unsaved creation — skip.
                pass

        # --- [Issue 1] Track capacity: max 2 vehicles per track per slot ---
        if self.track_id and self.slot_id and self.date:
            track_sessions = Session.objects.filter(
                date=self.date,
                slot=self.slot,
                track=self.track,
            )
            if self.pk:
                track_sessions = track_sessions.exclude(pk=self.pk)
            if track_sessions.count() >= 2:
                raise ValidationError(
                    f"Track '{self.track}' already has 2 vehicles assigned "
                    f"to {self.slot} on {self.date}. "
                    "Each track can handle at most 2 vehicles per slot."
                )

        # --- [Issue 2] Trainee daily session limit -------------------------
        if self.trainee_id and self.date:
            config = SchedulingConfig.load()
            daily_count = Session.objects.filter(
                trainee=self.trainee,
                date=self.date,
            ).exclude(pk=self.pk).count()

            if daily_count >= config.max_sessions_per_trainee_per_day:
                raise ValidationError(
                    f"Trainee '{self.trainee}' already has "
                    f"{daily_count} session(s) on {self.date}. "
                    f"The daily maximum is "
                    f"{config.max_sessions_per_trainee_per_day}."
                )

        # --- [Issue 6] session_type ↔ instructor — both directions --------
        if self.session_type == 'guided' and not self.instructor_id:
            raise ValidationError(
                "Guided sessions require an instructor to be assigned."
            )
        if self.session_type == 'unguided' and self.instructor_id:
            raise ValidationError(
                "Unguided sessions must not have an instructor assigned. "
                "Supervisor-only oversight applies to these sessions."
            )

        # --- [Issue 7] Supervisor must always be present -------------------
        if not self.supervisor_id:
            raise ValidationError(
                "Every session must have a supervisor assigned."
            )


        if self.trainee_id and self.trainee_type:
            try:
                # Re-fetch just the course_id from the Trainee row — avoids
                # loading the whole related Course object and is always accurate.
                from SDIMS_apps.trainees.models import Trainee as TraineeModel
                course_id    = TraineeModel.objects.filter(
                    pk=self.trainee_id
                ).values_list('course_id', flat=True).first()

                derived_type = 'course' if course_id else 'independent'

                if self.trainee_type != derived_type:
                    raise ValidationError(
                        f"trainee_type '{self.trainee_type}' does not match "
                        f"the trainee's actual enrollment state ('{derived_type}'). "
                        "Update the trainee's course enrollment or correct this field."
                    )
            except ValidationError:
                raise
            except Exception:
                # Relation not yet resolvable during unsaved creation — skip.
                pass

    # -----------------------------------------------------------------------
    # Convenience state-transition methods
    # -----------------------------------------------------------------------

    def approve(self, approving_user):
        """Transition: pending → scheduled."""
        if self.status != 'pending':
            raise ValidationError(
                f"Cannot approve a session with status '{self.status}'."
            )
        self.status      = 'scheduled'
        self.approved_by = approving_user
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    def cancel(self):
        """Cancel any session that hasn't already completed or been cancelled."""
        if self.status in ('completed', 'cancelled'):
            raise ValidationError(
                f"Cannot cancel a session with status '{self.status}'."
            )
        self.status = 'cancelled'
        self.save(update_fields=['status', 'updated_at'])

    def mark_ongoing(self):
        """Transition: scheduled → ongoing (triggered by Celery at slot start time)."""
        if self.status != 'scheduled':
            raise ValidationError(
                f"Cannot mark a session as ongoing from status '{self.status}'."
            )
        self.status = 'ongoing'
        self.save(update_fields=['status', 'updated_at'])


# 7. AttendanceRecord

class AttendanceRecord(models.Model):
    """
    Supervisor-marked attendance for one completed session.

    Saving with status='absent' fires a post_save signal (signals.py) that
    automatically creates a RescheduleQueue entry — no manual action needed.

    'late' is treated the same as 'present' for lesson-progress counting.
    """

    STATUS_CHOICES = [
        ('present', 'Present'),
        ('late',    'Late'),
        ('absent',  'Absent'),
    ]

    session   = models.OneToOneField(
        Session,
        on_delete=models.CASCADE,
        related_name='attendance',
    )
    status    = models.CharField(max_length=10, choices=STATUS_CHOICES)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='attendance_records_marked',
        help_text="Must be a supervisor or admin — enforced in the view layer.",
    )
    marked_at = models.DateTimeField(auto_now_add=True)
    notes     = models.TextField(blank=True)

    class Meta:
        ordering = ['-marked_at']

    def __str__(self):
        return f"{self.session} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Keep the parent Session in sync when attendance is recorded
        if self.session.status not in ('completed', 'cancelled'):
            self.session.status = 'completed'
            self.session.save(update_fields=['status', 'updated_at'])
        super().save(*args, **kwargs)


# 8. RescheduleQueue

class RescheduleQueue(models.Model):
    """
    Auto-populated when an AttendanceRecord with status='absent' is saved
    (post_save signal in signals.py).
    """

    trainee          = models.ForeignKey(
        'trainees.Trainee',
        on_delete=models.CASCADE,
        related_name='reschedule_queue_entries',
    )
    original_session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='reschedule_entries',
        help_text="The session that was missed (absent).",
    )

    priority = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=(
            "Manual urgency level: 1=critical, 5=low. "
            "Lower values are scheduled first. Set by admin or supervisor."
        ),
    )

    priority_score = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Auto-incremented on each failed scheduling attempt. "
            "Higher = more urgent within the same priority tier."
        ),
    )

    attempt_count     = models.PositiveSmallIntegerField(default=0)
    resolved          = models.BooleanField(default=False)
    resolved_session  = models.ForeignKey(
        Session,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='resolved_reschedule_entries',
        help_text="The new session that replaced the missed one.",
    )
    added_at          = models.DateTimeField(auto_now_add=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['priority', '-priority_score', 'attempt_count', 'added_at']
        verbose_name        = "Reschedule Queue Entry"
        verbose_name_plural = "Reschedule Queue"

    def __str__(self):
        state = "resolved" if self.resolved else f"attempt {self.attempt_count}"
        return f"{self.trainee} ({state}) — missed {self.original_session.date}"

    @property
    def is_maxed_out(self):
        config = SchedulingConfig.load()
        return (
            not self.resolved
            and self.attempt_count >= config.max_reschedule_attempts
        )

    def increment_attempt(self):
        self.attempt_count    += 1
        self.priority_score   += 1
        self.last_attempted_at = timezone.now()
        self.save(update_fields=[
            'attempt_count', 'priority_score', 'last_attempted_at'
        ])

    def resolve(self, new_session):
        self.resolved          = True
        self.resolved_session  = new_session
        self.last_attempted_at = timezone.now()
        self.save(update_fields=[
            'resolved', 'resolved_session', 'last_attempted_at'
        ])


# 9. RescheduleRequest  (trainee-initiated reschedule requests)

class RescheduleRequest(models.Model):
    """
    A trainee-initiated request to reschedule a specific upcoming session.

    Workflow:
      - Trainee submits via 'Request Reschedule' button on My Schedule page.
      - Supervisor/admin reviews and either approves or rejects.
      - On approval: the original session is cancelled and a RescheduleQueue
        entry is created so the scheduler picks the trainee up on the next run.
      - On rejection: the trainee's original session remains unchanged.

    Key rules:
      - Only sessions with status 'scheduled' or 'pending' may be requested.
      - A trainee cannot have two pending requests for the same session
        (enforced via UniqueConstraint + view-level guard).
    """

    STATUS_CHOICES = [
        ('pending',  'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    trainee    = models.ForeignKey(
        'trainees.Trainee',
        on_delete=models.CASCADE,
        related_name='reschedule_requests',
    )
    session    = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='reschedule_requests',
    )
    reason     = models.TextField(
        blank=True,
        help_text="Optional: trainee's reason for requesting a reschedule.",
    )
    status     = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
    )

    # --- Review fields (populated by supervisor/admin) --------------------
    reviewed_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_reschedule_requests',
        help_text="The supervisor or admin who handled this request.",
    )
    reviewed_at    = models.DateTimeField(null=True, blank=True)
    rejection_note = models.TextField(
        blank=True,
        help_text="Supervisor's note explaining why the request was rejected.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = "Reschedule Request"
        verbose_name_plural = "Reschedule Requests"
        constraints = [
            # Prevent duplicate pending requests for the same trainee+session.
            # A trainee can submit again only after a previous one is resolved.
            models.UniqueConstraint(
                fields=['trainee', 'session'],
                condition=models.Q(status='pending'),
                name='unique_pending_reschedule_request_per_trainee_session',
            ),
        ]

    def __str__(self):
        return (
            f"{self.trainee} → Session #{self.session_id} "
            f"[{self.get_status_display()}]"
        )

    def clean(self):
        super().clean()
        # Only allow requests for sessions that are still reschedulable.
        if self.session_id:
            reschedulable = ('scheduled', 'pending')
            if self.session.status not in reschedulable:
                raise ValidationError(
                    f"Cannot request a reschedule for a session with "
                    f"status '{self.session.status}'. "
                    "Only scheduled or pending sessions are eligible."
                )


# 10. PublicBooking  (walk-in / pay-per-session booking)

class PublicBooking(models.Model):
    """
    Standalone booking for walk-in / pay-per-session trainees.

    These are people who want a one-time or occasional driving practice
    session WITHOUT enrolling in a course or creating a user account.
    This model is completely independent of the Trainee/Session system.

    Workflow:
      1. Walk-in arrives at the institute (or calls ahead).
      2. Supervisor/admin creates a PublicBooking with guest info + slot.
      3. Resources (vehicle, track, optionally instructor) are assigned.
      4. Fee is charged immediately → fee_paid=True.
         OR fee is recorded as debt → fee_paid=False (outstanding).
      5. After the session: status → 'completed' or 'no_show'.

    Key rules:
      - Walk-ins do NOT get a User account or Trainee profile.
      - Their bookings consume only independent/leftover capacity.
      - The scheduler deducts confirmed PublicBookings from independent_remaining.
      - Unpaid bookings (fee_paid=False) are tracked as outstanding debt.
    """

    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show',   'No Show'),
    ]

    SESSION_TYPE_CHOICES = [
        ('guided',   'Guided (with instructor)'),
        ('unguided', 'Unguided (supervisor only)'),
    ]

    VEHICLE_TYPE_CHOICES = [
        ('car',     'Car'),
        ('bike',    'Bike'),
        ('scooter', 'Scooter'),
    ]

    # --- Guest information (no user account) ------------------------------

    guest_name = models.CharField(
        max_length=200,
        help_text="Full name of the walk-in trainee.",
    )
    guest_phone = models.CharField(
        max_length=15,
        help_text="Phone number for contact.",
    )
    guest_address = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional address.",
    )

    # --- Booking details --------------------------------------------------

    slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.PROTECT,
        related_name='public_bookings',
    )
    date = models.DateField()
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        help_text="The vehicle type requested for this session.",
    )
    session_type = models.CharField(
        max_length=10,
        choices=SESSION_TYPE_CHOICES,
        default='unguided',
        help_text="Whether an instructor is needed for this walk-in session.",
    )

    # --- Resource assignment (filled by supervisor/admin on confirmation) --

    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='public_bookings',
        help_text="Assigned vehicle.",
    )
    track = models.ForeignKey(
        Track,
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='public_bookings',
        help_text="Assigned track.",
    )
    instructor = models.ForeignKey(
        'instructors.Instructor',
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='public_bookings',
        help_text="Assigned instructor (guided sessions only).",
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name='public_bookings_supervised',
        help_text="The supervisor on duty.",
    )

    # --- Status -----------------------------------------------------------

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending',
    )

    # --- Fee & debt tracking ----------------------------------------------

    fee_amount = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text="Fee for this session (snapshot from SchedulingConfig at booking time).",
    )
    fee_paid = models.BooleanField(
        default=False,
        help_text=(
            "True = fee has been collected. "
            "False = outstanding debt (walk-in did not pay yet)."
        ),
    )

    # --- Audit ------------------------------------------------------------

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='public_bookings_created',
        help_text="The supervisor/admin who created this booking.",
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes        = models.TextField(
        blank=True,
        help_text="Internal notes about this booking.",
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name        = "Public Booking"
        verbose_name_plural = "Public Bookings"
        constraints = [
            models.UniqueConstraint(
                fields=['guest_phone', 'slot', 'date'],
                condition=models.Q(status__in=['pending', 'confirmed']),
                name='unique_active_public_booking_per_guest_slot_date',
            ),
        ]

    def __str__(self):
        return (
            f"{self.guest_name} → {self.slot} "
            f"on {self.date} [{self.get_status_display()}]"
        )

    @property
    def is_debt(self):
        """True if this booking is confirmed/completed but not yet paid."""
        return self.status in ('confirmed', 'completed') and not self.fee_paid

    def clean(self):
        super().clean()
        # Guided sessions require an instructor
        if self.status == 'confirmed':
            if self.session_type == 'guided' and not self.instructor_id:
                raise ValidationError(
                    "Guided public sessions require an instructor to be assigned."
                )
            if not self.vehicle_id:
                raise ValidationError(
                    "A vehicle must be assigned before confirming a public booking."
                )
            if not self.track_id:
                raise ValidationError(
                    "A track must be assigned before confirming a public booking."
                )
            if not self.supervisor_id:
                raise ValidationError(
                    "A supervisor must be assigned before confirming a public booking."
                )