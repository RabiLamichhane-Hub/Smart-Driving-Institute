from django import forms
from .models import RescheduleRequest, PublicBooking, SchedulingConfig, Track


class RescheduleRequestForm(forms.ModelForm):
    """
    Trainee-facing form for submitting a reschedule request.

    Only exposes the 'reason' field — trainees must never be able to set
    status, reviewed_by, reviewed_at, or rejection_note directly.
    """

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Optional: briefly explain why you need to reschedule…',
            'class': 'form-textarea',
        }),
        label='Reason (optional)',
    )

    class Meta:
        model  = RescheduleRequest
        fields = ['reason']


class PublicBookingForm(forms.ModelForm):
    """
    Supervisor/admin form to create a walk-in / pay-per-session booking.
    Collects guest info + booking details. Resources are assigned on confirmation.
    fee_amount is pre-populated from SchedulingConfig but can be overridden per booking.
    """

    fee_amount = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0,
        label='Session Fee (Rs.)',
        help_text='Pre-filled from Scheduling Config. Override for this booking only.',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '500.00',
            'step': '0.01',
        }),
    )

    class Meta:
        model  = PublicBooking
        fields = [
            'guest_name', 'guest_phone', 'guest_address',
            'slot', 'date', 'vehicle_type', 'vehicle', 'session_type',
            'fee_amount', 'notes',
        ]
        widgets = {
            'guest_name':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'guest_phone':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+977…'}),
            'guest_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address (optional)'}),
            'slot':          forms.Select(attrs={'class': 'form-select'}),
            'date':          forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'vehicle_type':  forms.Select(attrs={'class': 'form-select'}),
            'vehicle':       forms.Select(attrs={'class': 'form-select'}),
            'session_type':  forms.Select(attrs={'class': 'form-select'}),
            'notes':         forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Internal notes…'}),
        }

    def clean(self):
        cleaned = super().clean()
        booking_date = cleaned.get('date')
        if booking_date:
            from .scheduler import is_working_day
            if not is_working_day(booking_date):
                raise forms.ValidationError(
                    f"{booking_date} is a non-working day. Choose a working day."
                )
        return cleaned


class PublicBookingConfirmForm(forms.ModelForm):
    """
    Supervisor/admin form to assign resources and confirm a pending public booking.
    """

    fee_paid = forms.BooleanField(
        required=False,
        label='Fee collected?',
        help_text='Check if the walk-in has paid. Leave unchecked to record as debt.',
    )

    class Meta:
        model  = PublicBooking
        fields = ['vehicle', 'track', 'instructor', 'supervisor', 'fee_paid']
        widgets = {
            'vehicle':    forms.Select(attrs={'class': 'form-select'}),
            'track':      forms.Select(attrs={'class': 'form-select'}),
            'instructor': forms.Select(attrs={'class': 'form-select'}),
            'supervisor': forms.Select(attrs={'class': 'form-select'}),
        }


class TrackForm(forms.ModelForm):
    """
    Supervisor/admin form for creating and editing a Track.

    Covers all four editable fields on the model:
      - name        — unique identifier shown throughout the scheduler
      - track_type  — car | two_wheeler; drives is_compatible_with() logic
      - status      — active | inactive | maintenance
      - notes       — free-text internal remarks

    No cross-field validation is needed here: compatibility is enforced at
    the session/booking level via Track.is_compatible_with(), not at save time.
    """

    class Meta:
        model  = Track
        fields = ['name', 'track_type', 'status', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'e.g. Track A, North Circuit…',
                'maxlength':   50,
            }),
            'track_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'notes': forms.Textarea(attrs={
                'class':       'form-textarea',
                'rows':        3,
                'placeholder': 'Internal notes about this track (optional)…',
            }),
        }
        labels = {
            'name':       'Track Name',
            'track_type': 'Track Type',
            'status':     'Status',
            'notes':      'Notes',
        }
        help_texts = {
            'track_type': (
                'Car tracks accept cars only. '
                'Two-Wheeler tracks accept bikes and scooters. '
                'This cannot be changed once sessions are assigned to the track.'
            ),
            'status': (
                'Inactive and Under Maintenance tracks are excluded from '
                'automatic session scheduling.'
            ),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Track name cannot be blank.")
        # Enforce uniqueness manually so the error lands on the field,
        # not as a non-field __all__ error from the DB constraint.
        qs = Track.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f'A track named "{name}" already exists. Choose a different name.'
            )
        return name

    def clean_track_type(self):
        """
        Prevent changing track_type on an existing track that already has
        sessions assigned — doing so would silently break compatibility checks
        for all historical and future sessions on that track.
        """
        new_type = self.cleaned_data.get('track_type')
        if self.instance.pk and new_type != self.instance.track_type:
            from .models import Session
            session_count = Session.objects.filter(track=self.instance).count()
            if session_count > 0:
                raise forms.ValidationError(
                    f"Cannot change track type: {session_count} session(s) are already "
                    f"assigned to this track. Reassign them first."
                )
        return new_type