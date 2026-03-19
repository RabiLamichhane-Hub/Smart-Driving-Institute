from django.db import models
from django.core.exceptions import ValidationError
from SDIMS_apps.vehicles.models import Vehicle


class Course(models.Model):

    VEHICLE_TYPE_CHOICES = [
        ('car', 'Car'),
        ('bike', 'Bike / Motorcycle'),
        ('heavy', 'Heavy Vehicle'),
        ('tempo', 'Tempo / Mini Truck'),
    ]

    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    # Basic info
    course_name     = models.CharField(max_length=200)
    vehicle_type    = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES)
    level           = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    description     = models.TextField(blank=True)

    # 🔥 Vehicle relationship (FINAL)
    vehicles        = models.ManyToManyField(
        Vehicle,
        blank=True,
        related_name='courses'
    )

    # Duration & schedule
    duration_days   = models.PositiveIntegerField(help_text="Total course length in days")
    total_lessons   = models.PositiveIntegerField(help_text="Number of practical driving sessions")

    # Pricing
    fee             = models.DecimalField(max_digits=8, decimal_places=2)

    # Status
    is_active       = models.BooleanField(default=True)

    # Timestamps
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        🔒 Enforce: Vehicle type must match course vehicle type
        """
        if self.pk:  # Only check after instance is saved
            for vehicle in self.vehicles.all():
                if vehicle.vehicle_type != self.vehicle_type:
                    raise ValidationError(
                        f"{vehicle} does not match course vehicle type ({self.vehicle_type})"
                    )

    def __str__(self):
        return f"{self.course_name} ({self.get_vehicle_type_display()})"

    class Meta:
        ordering = ['vehicle_type', 'level']