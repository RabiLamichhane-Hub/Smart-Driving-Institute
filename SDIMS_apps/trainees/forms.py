from django import forms
from .models import Trainee

class TraineeForm(forms.ModelForm):
    class Meta:
        model = Trainee
        fields = [
            'gender',
            'date_of_birth',
            'course',
            'status',
            'guardian_name',
            'guardian_phone',
        ]