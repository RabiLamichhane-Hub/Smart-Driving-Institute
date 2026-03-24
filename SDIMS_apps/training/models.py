from django.db import models
from SDIMS_apps.instructors.models import Instructor
from SDIMS_apps.vehicles.models import Vehicle
from SDIMS_apps.trainees.models import Trainee

class TrainingSession(models.Model):
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE)
    trainee = models.ForeignKey(Trainee, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)

    session_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    def __str__(self):
        return f"{self.trainee} - {self.session_date}"