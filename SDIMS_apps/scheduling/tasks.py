"""
scheduling/tasks.py

Celery tasks for the Scheduling & Attendance module.

Tasks:
  - run_daily_scheduler        → runs every day at a configured time
  - mark_sessions_ongoing      → flips 'scheduled' → 'ongoing' at slot start
  - mark_sessions_completed    → flips 'ongoing' → 'completed' at slot end
  - send_schedule_reminders    → notifies trainees/instructors before their session

Setup required in settings.py:
  CELERY_BEAT_SCHEDULE = {
      'daily-scheduler': {
          'task': 'scheduling.tasks.run_daily_scheduler',
          'schedule': crontab(hour=22, minute=0),   # runs at 10 PM every night
      },
      'mark-ongoing': {
          'task': 'scheduling.tasks.mark_sessions_ongoing',
          'schedule': crontab(minute=0),            # runs every hour on the hour
      },
      'mark-completed': {
          'task': 'scheduling.tasks.mark_sessions_completed',
          'schedule': crontab(minute=0),            # runs every hour on the hour
      },
      'schedule-reminders': {
          'task': 'scheduling.tasks.send_schedule_reminders',
          'schedule': crontab(hour=20, minute=0),   # runs at 8 PM every night
      },
  }
"""

import logging
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# Task 1: Daily Scheduler

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,   # retry after 5 minutes on failure
    name='scheduling.tasks.run_daily_scheduler',
)
def run_daily_scheduler(self):
    """
    Runs every night (default 10 PM) to schedule sessions for the next day.
    Retries up to 3 times on failure before giving up.
    """
    from .models import SchedulingConfig
    from .scheduler import run_scheduler

    try:
        config      = SchedulingConfig.load()
        target_date = date.today() + timedelta(days=config.schedule_days_ahead)

        logger.info(
            "[run_daily_scheduler] Starting for target_date=%s", target_date
        )

        run = run_scheduler(target_date, triggered_by=None)

        logger.info(
            "[run_daily_scheduler] Completed — %d session(s) created for %s. "
            "Run ID: %s",
            run.sessions_created, target_date, run.pk,
        )

        return {
            'run_id':           run.pk,
            'target_date':      str(target_date),
            'sessions_created': run.sessions_created,
            'notes':            run.notes[:500] if run.notes else '',
        }

    except Exception as exc:
        logger.exception(
            "[run_daily_scheduler] Failed for target_date=%s — retrying.",
            date.today() + timedelta(days=1),
        )
        raise self.retry(exc=exc)


# Task 2: Mark Sessions Ongoing

@shared_task(
    name='scheduling.tasks.mark_sessions_ongoing',
)
def mark_sessions_ongoing():
    """
    Runs every hour on the hour.
    Finds all 'scheduled' sessions whose slot has started and flips them
    to 'ongoing' so supervisors see the correct live status.
    """
    from .models import Session

    now         = timezone.localtime(timezone.now())
    current_time = now.time()
    today        = now.date()

    # Find sessions scheduled for today whose slot start_time <= now
    sessions_to_update = Session.objects.filter(
        date=today,
        status='scheduled',
        slot__start_time__lte=current_time,
    ).select_related('slot')

    updated = 0
    for session in sessions_to_update:
        try:
            session.mark_ongoing()
            updated += 1
        except Exception as exc:
            logger.warning(
                "[mark_sessions_ongoing] Could not update session #%s: %s",
                session.pk, exc,
            )

    if updated:
        logger.info("[mark_sessions_ongoing] Marked %d session(s) as ongoing.", updated)

    return {'sessions_marked_ongoing': updated}


# Task 3: Mark Sessions Completed (if supervisor forgot to mark attendance)

@shared_task(
    name='scheduling.tasks.mark_sessions_completed',
)
def mark_sessions_completed():
    """
    Runs every hour on the hour.
    Finds 'ongoing' sessions whose slot end_time has passed and
    flips them to 'completed' so they don't stay stuck as 'ongoing'
    if a supervisor forgets to mark attendance.

    Note: This does NOT create an AttendanceRecord — that still requires
    the supervisor to act. This only cleans up the session status.
    """
    from .models import Session

    now          = timezone.localtime(timezone.now())
    current_time = now.time()
    today        = now.date()

    sessions_to_close = Session.objects.filter(
        date=today,
        status='ongoing',
        slot__end_time__lte=current_time,
    ).select_related('slot')

    updated = 0
    for session in sessions_to_close:
        try:
            session.status = 'completed'
            session.save(update_fields=['status', 'updated_at'])
            updated += 1
        except Exception as exc:
            logger.warning(
                "[mark_sessions_completed] Could not close session #%s: %s",
                session.pk, exc,
            )

    if updated:
        logger.info(
            "[mark_sessions_completed] Auto-closed %d session(s) to 'completed'.",
            updated,
        )

    return {'sessions_auto_completed': updated}


# Task 4: Send Schedule Reminders

@shared_task(
    name='scheduling.tasks.send_schedule_reminders',
)
def send_schedule_reminders():
    """
    Runs every evening (default 8 PM).
    Sends a reminder to each trainee and instructor who has a session
    scheduled for tomorrow.

    Uses Django's built-in send_mail. Replace with your preferred
    notification method (SMS, in-app notification, etc.) as needed.
    Currently only sends if the user has an email address set.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    from .models import Session

    tomorrow = date.today() + timedelta(days=1)

    sessions = Session.objects.filter(
        date=tomorrow,
        status='scheduled',
    ).select_related('trainee__user', 'instructor__user', 'slot', 'vehicle')

    sent_trainee    = 0
    sent_instructor = 0

    for session in sessions:
        slot_label = session.slot.label

        # --- Notify trainee ---
        trainee_email = session.trainee.user.email
        if trainee_email:
            try:
                send_mail(
                    subject=f"Reminder: Your driving session tomorrow — {slot_label}",
                    message=(
                        f"Hello {session.trainee.user.get_full_name()},\n\n"
                        f"This is a reminder that you have a driving session "
                        f"scheduled for tomorrow ({tomorrow}).\n\n"
                        f"Slot   : {slot_label}\n"
                        f"Vehicle: {session.vehicle}\n"
                        f"Track  : {session.track}\n\n"
                        f"Please arrive 5 minutes early.\n\n"
                        f"— SDIMS"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[trainee_email],
                    fail_silently=True,
                )
                sent_trainee += 1
            except Exception as exc:
                logger.warning(
                    "[send_schedule_reminders] Failed to email trainee %s: %s",
                    session.trainee, exc,
                )

        # --- Notify instructor (guided sessions only) ---
        if session.instructor and session.session_type == 'guided':
            instructor_email = session.instructor.user.email
            if instructor_email:
                try:
                    send_mail(
                        subject=f"Reminder: You have a session tomorrow — {slot_label}",
                        message=(
                            f"Hello {session.instructor.user.get_full_name()},\n\n"
                            f"You have a guided session scheduled for tomorrow "
                            f"({tomorrow}).\n\n"
                            f"Slot   : {slot_label}\n"
                            f"Trainee: {session.trainee.user.get_full_name()}\n"
                            f"Vehicle: {session.vehicle}\n"
                            f"Track  : {session.track}\n\n"
                            f"— SDIMS"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[instructor_email],
                        fail_silently=True,
                    )
                    sent_instructor += 1
                except Exception as exc:
                    logger.warning(
                        "[send_schedule_reminders] Failed to email instructor %s: %s",
                        session.instructor, exc,
                    )

    logger.info(
        "[send_schedule_reminders] Sent %d trainee + %d instructor reminder(s) "
        "for %s.",
        sent_trainee, sent_instructor, tomorrow,
    )

    return {
        'date':             str(tomorrow),
        'trainee_emails':   sent_trainee,
        'instructor_emails': sent_instructor,
    }