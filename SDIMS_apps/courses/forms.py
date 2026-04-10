from django import forms
from django.core.exceptions import ValidationError
from .models import Course
from SDIMS_apps.vehicles.models import Vehicle

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'course_name', 'vehicle_type', 'vehicle', 'level',
            'description', 'duration_days', 'total_lessons',
            'fee', 'is_active'
        ]
        widgets = {
            'course_name': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-select'}),
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 1, 'class': 'form-control'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_lessons': forms.NumberInput(attrs={'class': 'form-control'}),
            'fee': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.vehicle_type:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(
                vehicle_type=self.instance.vehicle_type
            )
        elif self.data.get('vehicle_type'):
            # POST request — use submitted vehicle_type to validate
            self.fields['vehicle'].queryset = Vehicle.objects.filter(
                vehicle_type=self.data.get('vehicle_type')
            )
        else:
            self.fields['vehicle'].queryset = Vehicle.objects.none()

    def clean_vehicle(self):
        vehicle = self.cleaned_data.get('vehicle')
        vehicle_type = self.cleaned_data.get('vehicle_type')
        if vehicle and vehicle_type and vehicle.vehicle_type != vehicle_type:
            raise forms.ValidationError(
                f"Selected vehicle does not match the course vehicle type."
            )
        return vehicle