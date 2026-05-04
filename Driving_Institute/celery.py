"""
celery.py — place this in your project root alongside settings.py

Project structure:
  SDIMS/                     ← project root (same folder as manage.py)
  ├── SDIMS/                 ← project package (same name, contains settings.py)
  │   ├── __init__.py
  │   ├── settings.py
  │   ├── urls.py
  │   └── celery.py          ← THIS FILE goes here
  ├── SDIMS_apps/
  │   └── scheduling/
  │       └── tasks.py
  └── manage.py
"""

import os
from celery import Celery
from celery.schedules import crontab

# Tell Celery which Django settings module to use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Driving_Institute')

app = Celery('Driving_Institute')

# Pull Celery config from Django settings — any key starting with CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks.py in every installed app
app.autodiscover_tasks()


# ---------------------------------------------------------------------------
# Beat schedule — periodic tasks
# ---------------------------------------------------------------------------

app.conf.beat_schedule = {

    # Run the scheduler every night at 10:00 PM
    # Generates sessions for the next day
    'daily-scheduler': {
        'task':     'SDIMS_apps.scheduling.tasks.run_daily_scheduler',
        'schedule': crontab(hour=22, minute=0),
    },

    # Every hour on the hour — flip 'scheduled' → 'ongoing' at slot start
    'mark-sessions-ongoing': {
        'task':     'SDIMS_apps.scheduling.tasks.mark_sessions_ongoing',
        'schedule': crontab(minute=0),
    },

    # Every hour on the hour — flip 'ongoing' → 'completed' at slot end
    'mark-sessions-completed': {
        'task':     'SDIMS_apps.scheduling.tasks.mark_sessions_completed',
        'schedule': crontab(minute=0),
    },

    # Every evening at 8:00 PM — email reminders for tomorrow's sessions
    'schedule-reminders': {
        'task':     'SDIMS_apps.scheduling.tasks.send_schedule_reminders',
        'schedule': crontab(hour=20, minute=0),
    },
}

app.conf.timezone = 'Asia/Kathmandu'   # NPT — change if needed


# ---------------------------------------------------------------------------
# Debug task — optional, useful during development
# ---------------------------------------------------------------------------

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')