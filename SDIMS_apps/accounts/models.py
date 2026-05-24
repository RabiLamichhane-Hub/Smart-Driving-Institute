from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('instructor', 'Instructor'),
        ('trainee', 'Trainee'),
        ('supervisor', 'Supervisor'),
    )
    first_name = models.CharField(max_length=150, blank=False)
    last_name = models.CharField(max_length=150, blank=False)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    phone = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?\d{7,15}$',
                message='Enter a valid phone number (digits only, 7–15 characters, optional leading +).',
            )
        ],
    )
    address = models.CharField(max_length=255, blank=False)
    email = models.EmailField(unique=True)

    must_change_password = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"