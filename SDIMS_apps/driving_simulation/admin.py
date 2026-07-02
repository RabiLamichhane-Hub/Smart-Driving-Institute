from django.contrib import admin
from .models import SimulationScenario, SimulationSession, CheckpointResult


class CheckpointResultInline(admin.TabularInline):
    model = CheckpointResult
    extra = 0
    readonly_fields = (
        'checkpoint_number',
        'time_at_checkpoint',
        'speed_at_checkpoint',
        'penalties_at_checkpoint',
    )
    can_delete = False


@admin.register(SimulationScenario)
class SimulationScenarioAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'scenario_type',
        'vehicle_type',
        'difficulty',
        'time_limit_seconds',
        'passing_score',
        'is_active',
    )
    list_filter = ('vehicle_type', 'difficulty', 'scenario_type', 'is_active')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    fieldsets = (
        (None, {
            'fields': ('name', 'scenario_type', 'vehicle_type', 'difficulty', 'description'),
        }),
        ('Rules & Scoring', {
            'fields': (
                'time_limit_seconds',
                'passing_score',
                'max_collisions_allowed',
                'total_checkpoints',
            ),
        }),
        ('Feature Toggles', {
            'fields': (
                'enable_traffic_signals',
                'enable_pedestrians',
                'enable_weather',
                'enable_reverse_parking',
            ),
            'classes': ('collapse',),
        }),
        ('Track Configuration', {
            'fields': ('track_config',),
            'classes': ('collapse',),
            'description': 'JSON track layout consumed by the Phaser simulator.',
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
    )


@admin.register(SimulationSession)
class SimulationSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'scenario',
        'status',
        'score',
        'passed',
        'collision_count',
        'signal_violations',
        'time_taken_display',
        'started_at',
    )
    list_filter = ('status', 'passed', 'scenario__vehicle_type', 'scenario__difficulty')
    search_fields = ('user__first_name', 'user__last_name', 'user__username')
    readonly_fields = (
        'session_id',
        'started_at',
        'completed_at',
    )
    inlines = [CheckpointResultInline]
    date_hierarchy = 'started_at'

    def time_taken_display(self, obj):
        return obj.duration_display
    time_taken_display.short_description = 'Duration'

    fieldsets = (
        (None, {
            'fields': ('session_id', 'user', 'scenario', 'status'),
        }),
        ('Scoring', {
            'fields': ('score', 'passed'),
        }),
        ('Telemetry', {
            'fields': (
                'time_taken_seconds',
                'total_distance',
                'max_speed_reached',
                'average_speed',
            ),
        }),
        ('Penalties', {
            'fields': (
                'collision_count',
                'signal_violations',
                'lane_violations',
                'speed_violations',
            ),
        }),
        ('Checkpoints', {
            'fields': ('checkpoints_cleared',),
        }),
        ('Parking', {
            'fields': (
                'parking_completed',
                'parking_accuracy',
                'parking_attempts',
            ),
            'classes': ('collapse',),
        }),
        ('Raw Data', {
            'fields': ('telemetry_data',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at'),
        }),
    )
