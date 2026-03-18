# courses/forms.py

from django import forms
from .models import Course

class CourseForm(forms.ModelForm):

    class Meta:
        model = Course
        fields = [
            'course_name',
            'vehicle_type',
            'level',
            'description',
            'duration_days',
            'total_lessons',
            'fee',
            'is_active',
        ]
        widgets = {
            'course_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Basic Car Driving Course',
            }),
            'vehicle_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'level': forms.Select(attrs={
                'class': 'form-select',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of the course...',
            }),
            'duration_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 30',
                'min': 1,
            }),
            'total_lessons': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 15',
                'min': 1,
            }),
            'fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 5000.00',
                'min': 0,
                'step': '0.01',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'course_name': 'Course Name',
            'vehicle_type': 'Vehicle Type',
            'level': 'Course Level',
            'description': 'Description',
            'duration_days': 'Duration (Days)',
            'total_lessons': 'Total Lessons',
            'fee': 'Course Fee (Rs.)',
            'is_active': 'Active Course',
        }

    def clean_fee(self):
        fee = self.cleaned_data.get('fee')
        if fee is not None and fee < 0:
            raise forms.ValidationError("Fee cannot be negative.")
        return fee

    def clean_total_lessons(self):
        lessons = self.cleaned_data.get('total_lessons')
        duration = self.cleaned_data.get('duration_days')
        if lessons and duration and lessons > duration:
            raise forms.ValidationError(
                "Total lessons cannot exceed duration in days."
            )
        return lessons