from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum
from SDIMS_apps.trainees.models import Trainee
from SDIMS_apps.courses.models import Course


class FeeRecord(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ]

    trainee = models.OneToOneField(
        Trainee,
        on_delete=models.CASCADE,
        related_name='fee_record'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        related_name='fee_records'
    )

    total_fee = models.DecimalField(max_digits=8, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unpaid')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # VALIDATION
    def clean(self):
        if self.discount_amount < 0:
            raise ValidationError("Discount cannot be negative.")
        if self.total_fee is not None and self.discount_amount > self.total_fee:
            raise ValidationError("Discount cannot exceed total fee.")

    # AUTO ASSIGN COURSE + FEE ON CREATION ONLY
    def save(self, *args, **kwargs):
        if not self.pk:
            if self.trainee.course:
                self.course = self.trainee.course
                self.total_fee = self.trainee.course.fee
                self.discount_amount = self.trainee.discount
        self.full_clean()
        super().save(*args, **kwargs)

    # CALCULATIONS (NO STORAGE)
    def final_fee(self):
        return self.total_fee - self.discount_amount

    def total_paid(self):
        return self.payments.aggregate(total=Sum('amount'))['total'] or 0

    def remaining(self):
        return self.final_fee() - self.total_paid()

    # STATUS UPDATE
    def update_status(self, commit=True):
        paid = self.total_paid()
        total = self.final_fee()

        if paid <= 0:
            self.status = 'unpaid'
        elif paid >= total:
            self.status = 'paid'
        else:
            self.status = 'partial'

        if commit:
            super().save(update_fields=['status'])

    def __str__(self):
        return f"{self.trainee} — {self.status} (Rs.{self.remaining()} remaining)"


class Payment(models.Model):
    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('online', 'Online'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    fee_record = models.ForeignKey(
        FeeRecord,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payments_received'
    )

    date = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-date']

    # VALIDATION — excludes self to handle edits correctly
    def clean(self):
        if not self.fee_record_id:
            return

        if self.amount <= 0:
            raise ValidationError("Payment must be greater than zero.")

        existing_paid = (
            self.fee_record.payments
            .exclude(pk=self.pk)
            .aggregate(total=Sum('amount'))['total'] or 0
        )
        remaining = self.fee_record.final_fee() - existing_paid

        if self.amount > remaining:
            raise ValidationError(
                f"Payment exceeds remaining balance (Rs.{remaining:.2f})."
            )

    # SAVE + STATUS UPDATE
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.fee_record.update_status()

    def __str__(self):
        return f"{self.fee_record.trainee} — Rs.{self.amount} via {self.get_method_display()}"


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('fuel', 'Fuel'),
        ('snacks', 'Snacks'),
        ('maintenance', 'Maintenance'),
        ('salary', 'Salary'),
        ('rent', 'Rent'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='expenses_recorded'
    )

    date = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-date']

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Expense amount must be greater than zero.")

    # Calls full_clean() so clean() is never silently skipped
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} — Rs.{self.amount} ({self.category})"