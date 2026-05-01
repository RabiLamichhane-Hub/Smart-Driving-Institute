from django.contrib import admin
from . models import Track
from . models import TimeSlot
from . models import SchedulingConfig
from . models import TraineePreference
from . models import DailyScheduleRun
from . models import Session
from . models import AttendanceRecord
from . models import RescheduleQueue

# Register your models here.

admin.site.register(Track)
admin.site.register(TimeSlot)
admin.site.register(SchedulingConfig)
admin.site.register(TraineePreference)
admin.site.register(DailyScheduleRun)
admin.site.register(Session)
admin.site.register(AttendanceRecord)
admin.site.register(RescheduleQueue)