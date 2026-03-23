from django import forms
from .models import Vehicle

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = '__all__'
    widgets = {
        'last_service_date': forms.DateInput(attrs={'type': 'date'}),
        'insurance_expiry': forms.DateInput(attrs={'type': 'date'}),
    }