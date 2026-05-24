from django import forms
from .models import Trainee


class TraineeForm(forms.ModelForm):
    class Meta:
        model = Trainee
        fields = [
            'gender',
            'date_of_birth',
            'course',
            'discount',
            'status',
            'instructor_guidance',
            'vehicle_type_preference',
            'guardian_name',
            'guardian_phone',
            'images',
        ]
        widgets = {
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'course': forms.Select(attrs={'class': 'form-select', 'id': 'id_course'}),
            'discount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0',
                'min': '0',
                'id': 'id_discount',
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'instructor_guidance': forms.Select(attrs={'class': 'form-select'}),
            'vehicle_type_preference': forms.Select(attrs={'class': 'form-select'}),
            'guardian_name': forms.TextInput(attrs={'class': 'form-control'}),
            'guardian_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'images': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }