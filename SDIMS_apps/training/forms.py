from django import forms
from .models import TrainingSession, Attendance

class TrainingSessionForm(forms.ModelForm):
    class Meta:
        model = TrainingSession
        fields = '__all__'
        widgets = {
            'session_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        instructor = cleaned_data.get('instructor')
        vehicle = cleaned_data.get('vehicle')
        date = cleaned_data.get('session_date')
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')

        # ✅ 1. Basic time validation
        if start and end:
            if start >= end:
                raise forms.ValidationError("End time must be after start time.")

        # If any required field missing, skip further checks
        if not all([instructor, vehicle, date, start, end]):
            return cleaned_data

        # ✅ 2. Instructor conflict check
        instructor_conflict = TrainingSession.objects.filter(
            instructor=instructor,
            session_date=date,
            start_time__lt=end,
            end_time__gt=start
        )

        # Exclude current instance when updating
        if self.instance.pk:
            instructor_conflict = instructor_conflict.exclude(pk=self.instance.pk)

        if instructor_conflict.exists():
            raise forms.ValidationError("Instructor is already booked for this time.")

        # ✅ 3. Vehicle conflict check
        vehicle_conflict = TrainingSession.objects.filter(
            vehicle=vehicle,
            session_date=date,
            start_time__lt=end,
            end_time__gt=start
        )

        if self.instance.pk:
            vehicle_conflict = vehicle_conflict.exclude(pk=self.instance.pk)

        if vehicle_conflict.exists():
            raise forms.ValidationError("Vehicle is already in use at this time.")

        return cleaned_data
    

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['status', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional notes...'
            }),
        }