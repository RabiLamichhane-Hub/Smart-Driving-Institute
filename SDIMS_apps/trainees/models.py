from django.db import models
from django.conf import settings
from SDIMS_apps.courses.models import Course

User = settings.AUTH_USER_MODEL


class Trainee(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )

    STATUS_CHOICES = (
        ('ENROLLED', 'Enrolled'),
        ('TRAINING', 'In Training'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('PAY_PER_SESSION', 'Pay-Per-Session'),
    )

    GUIDANCE_CHOICES = (
        ('guided', 'Instructor-Guided'),
        ('free', 'Instructor-Free'),
    )

    VEHICLE_TYPE_CHOICES = (
        ('car', 'Car'),
        ('bike', 'Bike'),
        ('scooter', 'Scooter'),
    )

    # LINK TO USER
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # KEEP ONLY trainee-specific data
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()

    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trainees'
    )

    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ENROLLED')

    # --- Instructor guidance override ---
    # Supervisors/admins can manually classify trainees as guided or free.
    # 'auto' = system determines based on course level or policy.
    instructor_guidance = models.CharField(
        max_length=10,
        choices=GUIDANCE_CHOICES,
        default='auto',
        help_text=(
            "Manual override for instructor requirement. "
            "'auto' = system determines based on course level or policy. "
            "Set by supervisor/admin."
        ),
    )

    # --- Vehicle type preference (for pay-per-session trainees) ---
    # Required when no course is assigned, since there's no course.vehicle_type
    # to fall back on.
    vehicle_type_preference = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="Vehicle type for pay-per-session trainees who have no course.",
    )

    # Optional
    guardian_name = models.CharField(max_length=150, blank=True, null=True)
    guardian_phone = models.CharField(max_length=15, blank=True, null=True)

    # Photo
    images = models.ImageField(
        upload_to='trainees/images/',
        blank=True,
        null=True
    )

    # Discount
    discount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Flat discount amount in Rs."
    )

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def is_active_trainee(self):
        return self.status in ['ENROLLED', 'TRAINING', 'PAY_PER_SESSION']

    @property
    def is_pay_per_session(self):
        """True if this trainee has no course enrollment."""
        return self.course_id is None

    @property
    def effective_guidance(self):
        """
        Resolve the actual guidance mode after applying policy.
        Priority: manual override > course-level auto-policy > default free.
        """
        if self.instructor_guidance != 'auto':
            return self.instructor_guidance
        # Auto policy: course beginners/intermediates = guided, else free
        if self.course and self.course.level in ('beginner', 'intermediate'):
            return 'guided'
        return 'free'

    @property
    def effective_vehicle_type(self):
        """
        Returns the vehicle type to use for scheduling.
        Course trainees use their course's vehicle_type.
        Pay-per-session trainees use vehicle_type_preference.
        """
        if self.course:
            return self.course.vehicle_type
        return self.vehicle_type_preference

    @property
    def final_fee(self):
        """Returns the course fee after applying the flat discount.
        Returns 0 if no course is assigned."""
        if self.course and self.course.fee:
            return max(self.course.fee - self.discount, 0)
        return 0