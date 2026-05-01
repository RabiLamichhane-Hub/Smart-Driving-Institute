from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


# 1. Track

class Track(models.Model):
    """
    Physical driving track on the premises.
    Rule: 1 track handles at most 2 vehicles simultaneously per slot.
    This is enforced in Session.clean() — not here — because it depends
    on cross-row aggregate logic.
    """

    STATUS_CHOICES = [
        ('active',       'Active'),
        ('inactive',     'Inactive'),
        ('maintenance',  'Under Maintenance'),
    ]

    name   = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes  = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# 2. TimeSlot  (seeded once — never created via UI)

class TimeSlot(models.Model):
    """
    Fixed, non-overlapping 2-hour slots shared across all days.
    Populated via: python manage.py seed_slots
    Slot numbers: 1=06:00, 2=08:00, 3=10:00, 4=14:00, 5=16:00, 6=18:00
    """

    slot_number = models.PositiveSmallIntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(6)],
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
            if (end_dt - start_dt).seconds != 7200:
                raise ValidationError("Each slot must be exactly 2 hours.")


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
        validators=[MinValueValidator(1), MaxValueValidator(6)],
        help_text="1 = top choice, 6 = last resort.",
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