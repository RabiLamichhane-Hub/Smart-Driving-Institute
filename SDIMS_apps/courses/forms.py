from django import forms
from .models import Course
from SDIMS_apps.vehicles.models import Vehicle


class CourseForm(forms.ModelForm):

    class Meta:
        model = Course
        fields = [
            'course_name',
            'vehicle_type',
            'vehicles',   # 🔥 ADDED
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

            # 🔥 VEHICLE FIELD UI
            'vehicles': forms.SelectMultiple(attrs={
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
            'vehicles': 'Select Vehicles',  # 🔥 ADDED
            'level': 'Course Level',
            'description': 'Description',
            'duration_days': 'Duration (Days)',
            'total_lessons': 'Total Lessons',
            'fee': 'Course Fee (Rs.)',
            'is_active': 'Active Course',
        }

    # 🔥 DYNAMIC FILTERING
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['vehicles'].queryset = Vehicle.objects.none()

        # When form is submitted (POST)
        if 'vehicle_type' in self.data:
            vehicle_type = self.data.get('vehicle_type')
            self.fields['vehicles'].queryset = Vehicle.objects.filter(
                status='available',
                vehicle_type=vehicle_type
            )

        # When editing existing instance
        elif self.instance.pk:
            self.fields['vehicles'].queryset = Vehicle.objects.filter(
                status='available',
                vehicle_type=self.instance.vehicle_type
            )

    # 🔒 VALIDATION (VERY IMPORTANT)
    def clean_vehicles(self):
        vehicles = self.cleaned_data.get('vehicles')
        vehicle_type = self.cleaned_data.get('vehicle_type')

        for vehicle in vehicles:
            if vehicle.vehicle_type != vehicle_type:
                raise forms.ValidationError(
                    f"{vehicle} does not match selected vehicle type."
                )

        return vehicles

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