from django.db import models
from django.conf import settings
from SDIMS_apps.courses.models import Course

User = settings.AUTH_USER_MODEL


class Trainee(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )

    STATUS_CHOICES = (
        ('ENROLLED', 'Enrolled'),
        ('TRAINING', 'In Training'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    )

    #LINK TO USER
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # KEEP ONLY trainee-specific data
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()

    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trainees'
    )

    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ENROLLED')

    # Optional
    guardian_name = models.CharField(max_length=150, blank=True, null=True)
    guardian_phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def is_active_trainee(self):
        return self.status in ['ENROLLED', 'TRAINING']