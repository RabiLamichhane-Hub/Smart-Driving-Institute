from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from .scheduler import is_working_day
from .models import HolidayOrDayOff

User = get_user_model()

class IsWorkingDayTests(TestCase):
    def test_saturday_is_not_working(self):
        # Find next Saturday
        today = date.today()
        days_ahead = (5 - today.weekday()) % 7 or 7
        saturday = today + timedelta(days=days_ahead)
        self.assertFalse(is_working_day(saturday))

    def test_monday_is_working(self):
        today = date.today()
        days_ahead = (0 - today.weekday()) % 7 or 7
        monday = today + timedelta(days=days_ahead)
        self.assertTrue(is_working_day(monday))

    def test_declared_holiday_is_not_working(self):
        holiday_date = date(2026, 6, 15)
        HolidayOrDayOff.objects.create(date=holiday_date, reason="Test holiday")
        self.assertFalse(is_working_day(holiday_date))
