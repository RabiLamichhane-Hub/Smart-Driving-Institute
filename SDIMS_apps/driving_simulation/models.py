import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class SimulationScenario(models.Model):
    """
    Admin-configurable driving scenario / track template.
    Each scenario defines the rules, vehicle type, time limit, and
    difficulty for a simulation session.
    """

    VEHICLE_TYPE_CHOICES = [
        ('car', 'Car (4-Wheeler)'),
        ('bike', 'Bike (2-Wheeler)'),
        ('scooter', 'Scooter'),
    ]

    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    SCENARIO_TYPE_CHOICES = [
        ('city_driving', 'City Driving'),
        ('highway', 'Highway Driving'),
        ('reverse_parking', 'Reverse Parking'),
        ('parallel_parking', 'Parallel Parking'),
        ('traffic_signals', 'Traffic Signals'),
        ('hill_driving', 'Hill Driving'),
        ('night_driving', 'Night Driving'),
        ('figure_eight', 'Figure-8 Course'),
        ('free_roam', 'Free Roam'),
    ]

    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Display name for the scenario (e.g. 'City Driving – Easy')"
    )
    scenario_type = models.CharField(
        max_length=30,
        choices=SCENARIO_TYPE_CHOICES,
        default='city_driving',
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        default='car',
    )
    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default='medium',
    )
    description = models.TextField(
        blank=True,
        help_text="Brief description shown to the trainee before starting."
    )

    # Scoring & rules
    time_limit_seconds = models.PositiveIntegerField(
        default=180,
        help_text="Maximum time allowed for this scenario (seconds)."
    )
    passing_score = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum score (0-100) required to pass."
    )
    max_collisions_allowed = models.PositiveIntegerField(
        default=3,
        help_text="Maximum boundary/obstacle collisions before auto-fail."
    )
    total_checkpoints = models.PositiveIntegerField(
        default=5,
        help_text="Number of checkpoints on the track."
    )

    # Feature toggles – which simulation sub-systems are enabled
    enable_traffic_signals = models.BooleanField(
        default=True,
        help_text="Enable traffic signal logic (red/yellow/green)."
    )
    enable_pedestrians = models.BooleanField(
        default=False,
        help_text="Spawn AI pedestrians on the track."
    )
    enable_weather = models.BooleanField(
        default=False,
        help_text="Enable dynamic weather effects (rain, fog)."
    )
    enable_reverse_parking = models.BooleanField(
        default=False,
        help_text="Include a reverse-parking challenge segment."
    )

    # Track data – stored as JSON for Phaser to consume
    track_config = models.JSONField(
        blank=True,
        null=True,
        help_text=(
            "JSON configuration for the track layout consumed by Phaser. "
            "Contains boundaries, checkpoint positions, spawn point, etc."
        )
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vehicle_type', 'difficulty', 'name']
        verbose_name = 'Simulation Scenario'
        verbose_name_plural = 'Simulation Scenarios'

    def __str__(self):
        return f"{self.name} ({self.get_vehicle_type_display()} – {self.get_difficulty_display()})"


class SimulationSession(models.Model):
    """
    Records a single simulation attempt by a trainee.
    Created when the trainee starts a simulation; updated with
    results when the session ends (Phaser POSTs back).
    """

    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('abandoned', 'Abandoned'),
    ]

    # Unique session token sent to Phaser so the JS can POST results back
    session_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='simulation_sessions',
    )
    scenario = models.ForeignKey(
        SimulationScenario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='in_progress',
    )

    # ── Scoring ──────────────────────────────────────
    score = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Final calculated score (0-100)."
    )
    passed = models.BooleanField(default=False)

    # ── Driving telemetry ────────────────────────────
    time_taken_seconds = models.FloatField(
        default=0,
        help_text="Actual time the trainee took (seconds)."
    )
    total_distance = models.FloatField(
        default=0,
        help_text="Total distance covered in game units."
    )
    max_speed_reached = models.FloatField(
        default=0,
        help_text="Peak speed recorded during the session."
    )
    average_speed = models.FloatField(
        default=0,
        help_text="Average speed over the session."
    )

    # ── Penalty counters ─────────────────────────────
    collision_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of boundary/obstacle collisions."
    )
    signal_violations = models.PositiveIntegerField(
        default=0,
        help_text="Number of red-light / signal violations."
    )
    lane_violations = models.PositiveIntegerField(
        default=0,
        help_text="Number of wrong-lane / off-road violations."
    )
    speed_violations = models.PositiveIntegerField(
        default=0,
        help_text="Number of over-speed violations."
    )

    # ── Checkpoint tracking ──────────────────────────
    checkpoints_cleared = models.PositiveIntegerField(
        default=0,
        help_text="How many checkpoints the trainee passed through."
    )

    # ── Reverse parking (if applicable) ──────────────
    parking_completed = models.BooleanField(
        default=False,
        help_text="Whether the parking challenge was completed."
    )
    parking_accuracy = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Parking accuracy percentage (0-100)."
    )
    parking_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of parking attempts."
    )

    # ── Raw telemetry blob (optional) ────────────────
    telemetry_data = models.JSONField(
        blank=True,
        null=True,
        help_text="Raw JSON telemetry from the Phaser simulation for replay/analysis."
    )

    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Simulation Session'
        verbose_name_plural = 'Simulation Sessions'

    def __str__(self):
        scenario_name = self.scenario.name if self.scenario else 'Unknown'
        return (
            f"{self.user} — {scenario_name} — "
            f"{self.score}/100 on {self.started_at.strftime('%Y-%m-%d %H:%M')}"
        )

    @property
    def penalty_count(self):
        """Total penalty events across all categories."""
        return (
            self.collision_count
            + self.signal_violations
            + self.lane_violations
            + self.speed_violations
        )

    @property
    def duration_display(self):
        """Human-readable duration string."""
        mins, secs = divmod(int(self.time_taken_seconds), 60)
        return f"{mins}m {secs}s"


class CheckpointResult(models.Model):
    """
    Per-checkpoint timing/penalty breakdown within a session.
    Allows granular analysis of which track sections are problematic.
    """

    session = models.ForeignKey(
        SimulationSession,
        on_delete=models.CASCADE,
        related_name='checkpoint_results',
    )
    checkpoint_number = models.PositiveIntegerField(
        help_text="1-indexed checkpoint order on the track."
    )
    time_at_checkpoint = models.FloatField(
        help_text="Elapsed time (seconds) when this checkpoint was reached."
    )
    speed_at_checkpoint = models.FloatField(
        default=0,
        help_text="Vehicle speed when crossing this checkpoint."
    )
    penalties_at_checkpoint = models.PositiveIntegerField(
        default=0,
        help_text="Cumulative penalties up to this checkpoint."
    )

    class Meta:
        ordering = ['session', 'checkpoint_number']
        unique_together = ['session', 'checkpoint_number']
        verbose_name = 'Checkpoint Result'
        verbose_name_plural = 'Checkpoint Results'

    def __str__(self):
        return f"Session {self.session.session_id} — CP {self.checkpoint_number}"
