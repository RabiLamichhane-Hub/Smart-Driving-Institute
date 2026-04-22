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
            'guardian_name',
            'guardian_phone',
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
            'guardian_name': forms.TextInput(attrs={'class': 'form-control'}),
            'guardian_phone': forms.TextInput(attrs={'class': 'form-control'}),
        }