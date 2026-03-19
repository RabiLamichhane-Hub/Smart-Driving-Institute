
from django.db import models

class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ('car', 'Car'),
        ('bike', 'Bike'),
        ('scooter', 'Scooter'),
    ]

    TRANSMISSION_CHOICES = [
        ('manual', 'Manual'),
        ('automatic', 'Automatic'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('maintenance', 'Maintenance'),
    ]

    FUEL_TYPE_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric')
    ]

    name = models.CharField(max_length=100)
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES)
    transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES)

    registration_number = models.CharField(max_length=50, unique=True)
    bluebook_number = models.CharField(max_length=50)
    engine_number = models.CharField(max_length=50)
    chassis_number = models.CharField(max_length=50)

    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPE_CHOICES)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    last_service_date = models.DateField(null=True, blank=True)
    insurance_expiry = models.DateField(null=True, blank=True)

    dual_control = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.brand} {self.model} ({self.registration_number})"