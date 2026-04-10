from django.db import models
from django.core.exceptions import ValidationError
from SDIMS_apps.vehicles.models import Vehicle

class Course(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    # Use same choices as Vehicle
    VEHICLE_TYPE_CHOICES = Vehicle.VEHICLE_TYPE_CHOICES

    # Basic info
    course_name = models.CharField(max_length=200, unique=True)
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        help_text="Select the type of vehicle for this course"
    )
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    description = models.TextField(blank=True)

    # Available vehicles for this course
    vehicle = models.ForeignKey(
        Vehicle,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='courses',
        help_text="Select a vehicle for this course"
    )

    # Duration & schedule
    duration_days = models.PositiveIntegerField(help_text="Total course length in days")
    total_lessons = models.PositiveIntegerField(help_text="Number of practical driving sessions")

    # Pricing
    fee = models.DecimalField(max_digits=8, decimal_places=2)

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vehicle_type', 'level', 'course_name']

    def __str__(self):
        return f"{self.course_name} ({self.get_vehicle_type_display()})"

    def clean(self):
        if self.vehicle and self.vehicle.vehicle_type != self.vehicle_type:
            raise ValidationError(
                f"Selected vehicle ({self.vehicle}) does not match the course vehicle type ({self.get_vehicle_type_display()})."
            )
        if self.duration_days and self.duration_days <= 0:
            raise ValidationError("Duration must be greater than 0 days.")
        if self.total_lessons and self.total_lessons <= 0:
            raise ValidationError("Total lessons must be greater than 0.")
        if self.fee and self.fee <= 0:
            raise ValidationError("Fee must be greater than 0.")