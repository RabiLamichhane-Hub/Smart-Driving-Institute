from django.db import models
from SDIMS_apps.courses.models import Course


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

    # Basic Info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()

    # Contact Info
    phone = models.CharField(max_length=10, unique=True)
    email = models.EmailField(unique=True)
    address = models.CharField(max_length=50)

    # 🔥 COURSE INFO (ADD THIS)
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trainees'
    )
    enrollment_date = models.DateField(auto_now_add=True)

    # Progress Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ENROLLED')

    # Optional
    guardian_name = models.CharField(max_length=150, blank=True, null=True)
    guardian_phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def is_active_trainee(self):
        return self.status in ['ENROLLED', 'TRAINING']