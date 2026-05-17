from django.contrib import admin
from . models import Track
from . models import TimeSlot
from . models import SchedulingConfig
from . models import TraineePreference
from . models import DailyScheduleRun
from . models import Session
from . models import AttendanceRecord
from . models import RescheduleQueue
from . models import RescheduleRequest
from .models import HolidayOrDayOff

# Register your models here.

admin.site.register(Track)
admin.site.register(TimeSlot)
admin.site.register(SchedulingConfig)
admin.site.register(TraineePreference)
admin.site.register(DailyScheduleRun)
admin.site.register(Session)
admin.site.register(AttendanceRecord)
admin.site.register(RescheduleQueue)
admin.site.register(RescheduleRequest)

@admin.register(HolidayOrDayOff)
class HolidayOrDayOffAdmin(admin.ModelAdmin):
    list_display  = ('date', 'reason', 'declared_by', 'declared_at')
    list_filter   = ('declared_at',)
    search_fields = ('date', 'reason')
    ordering      = ('date',)