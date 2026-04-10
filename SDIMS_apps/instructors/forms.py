from django import forms
from .models import Instructor

class InstructorForm(forms.ModelForm):
    class Meta:
        model = Instructor
        fields = [
            'license_number',
            'status',
        ]