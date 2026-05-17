from django import forms
from .models import RescheduleRequest


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