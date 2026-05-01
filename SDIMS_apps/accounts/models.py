from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('instructor', 'Instructor'),
        ('trainee', 'Trainee'),
        ('supervisor', 'Supervisor'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    phone = models.CharField(max_length=15)
    address = models.CharField(max_length=255)
    email = models.EmailField(unique=True)

    must_change_password = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"