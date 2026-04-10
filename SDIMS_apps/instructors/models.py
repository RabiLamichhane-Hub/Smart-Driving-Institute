from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Instructor(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # REMOVE duplicated fields like email, phone
    license_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    date_joined = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"