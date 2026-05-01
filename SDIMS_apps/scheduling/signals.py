"""
scheduling/signals.py

Bug fix applied:
  [Bug 6] advance_lesson_progress now guards against double-counting
           when an attendance record is updated (not just created).
           We track the previous status via a pre_save signal and only
           increment when a new 'present'/'late' record is being added,
           or when a record changes FROM a non-counting status TO a
           counting one. Corrections in the other direction (present →
           absent) are also handled correctly.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import AttendanceRecord, RescheduleQueue


# Signal 1: Absent → auto-create RescheduleQueue entry

@receiver(post_save, sender=AttendanceRecord)
def auto_enqueue_reschedule(sender, instance, created, **kwargs):
    """
    Fires after every AttendanceRecord save.
    If the trainee was marked Absent, create a RescheduleQueue entry
    (or re-open an existing resolved one for the same original session).
    """
    if instance.status != 'absent':
        return

    queue_entry, created_entry = RescheduleQueue.objects.get_or_create(
        trainee          = instance.session.trainee,
        original_session = instance.session,
        defaults={
            'resolved':       False,
            'attempt_count':  0,
            'priority':       3,
            'priority_score': 0,
        },
    )

    # If the entry existed but was previously resolved (edge case: marked
    # absent again after a correction), re-open it.
    if not created_entry and queue_entry.resolved:
        queue_entry.resolved         = False
        queue_entry.resolved_session = None
        queue_entry.attempt_count    = 0
        queue_entry.priority_score   = 0
        queue_entry.save(update_fields=[
            'resolved', 'resolved_session', 'attempt_count', 'priority_score'
        ])


# Signal 2 (pre_save): Capture previous status before overwrite

@receiver(pre_save, sender=AttendanceRecord)
def capture_previous_attendance_status(sender, instance, **kwargs):
    """
    FIX [Bug 6]: Store the old status on the instance before it is
    overwritten, so post_save can detect whether this is a real new
    attendance event or just a correction within the same category.
    """
    if instance.pk:
        try:
            instance._previous_status = AttendanceRecord.objects.filter(
                pk=instance.pk
            ).values_list('status', flat=True).get()
        except AttendanceRecord.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None   # brand-new record

# Signal 3 (post_save): Advance lesson progress + check completion

COUNTING_STATUSES = {'present', 'late'}


@receiver(post_save, sender=AttendanceRecord)
def advance_lesson_progress(sender, instance, created, **kwargs):
    """
    FIX [Bug 6]: Only recalculate lesson progress when the effective
    "count" changes — i.e. when:
      - A new record is saved as present/late  (created=True)
      - An existing record changes from absent → present/late
      - An existing record changes from present/late → absent
        (need to re-count in case of correction)

    Skipping unchanged saves (present → present, absent → absent) avoids
    double-counting and unnecessary DB writes.
    """
    trainee = instance.session.trainee

    # Only applies to trainees enrolled in a course
    if not hasattr(trainee, 'course') or trainee.course is None:
        return

    previous = getattr(instance, '_previous_status', None)
    current  = instance.status

    prev_counted = previous in COUNTING_STATUSES
    curr_counted = current  in COUNTING_STATUSES

    # No change in whether this record counts → nothing to do
    if prev_counted == curr_counted:
        return

    # Recalculate from scratch to stay accurate regardless of edit direction
    attended_count = AttendanceRecord.objects.filter(
        session__trainee=trainee,
        status__in=COUNTING_STATUSES,
    ).count()

    total_lessons = trainee.course.total_lessons

    if attended_count >= total_lessons:
        if trainee.status != 'COMPLETED':
            trainee.status = 'COMPLETED'
            trainee.save(update_fields=['status'])
    elif attended_count > 0:
        if trainee.status == 'ENROLLED':
            trainee.status = 'TRAINING'
            trainee.save(update_fields=['status'])
    else:
        # All attended sessions were corrected away — revert to ENROLLED
        if trainee.status == 'TRAINING':
            trainee.status = 'ENROLLED'
            trainee.save(update_fields=['status'])