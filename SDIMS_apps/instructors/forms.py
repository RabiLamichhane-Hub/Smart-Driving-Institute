from django import forms
from .models import Instructor

class InstructorForm(forms.ModelForm):
    class Meta:
        model = Instructor
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'license_number', 'status']