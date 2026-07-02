import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Avg, Max, Count, Q, F

from .models import SimulationScenario, SimulationSession, CheckpointResult


# ══════════════════════════════════════════════════════════════
#  SIMULATOR  – main page (renders the Phaser game)
# ══════════════════════════════════════════════════════════════

@login_required
def simulator(request):
    """
    GET /simulation/
    Renders the simulator page. If a scenario_id is provided via query
    param, that specific scenario is loaded; otherwise a scenario picker
    is shown.
    """
    scenario_id = request.GET.get('scenario')
    scenarios = SimulationScenario.objects.filter(is_active=True)

    selected_scenario = None
    session = None

    if scenario_id:
        selected_scenario = get_object_or_404(
            SimulationScenario, pk=scenario_id, is_active=True
        )
        # Create an in-progress session so Phaser can reference it
        session = SimulationSession.objects.create(
            user=request.user,
            scenario=selected_scenario,
            status='in_progress',
        )

    # Determine vehicle type filter from user's trainee profile
    vehicle_type_filter = None
    if hasattr(request.user, 'trainee'):
        vehicle_type_filter = request.user.trainee.effective_vehicle_type

    if vehicle_type_filter:
        scenarios = scenarios.filter(vehicle_type=vehicle_type_filter)

    context = {
        'scenarios': scenarios,
        'selected_scenario': selected_scenario,
        'session': session,
        'session_id': str(session.session_id) if session else None,
        'scenario_config': json.dumps(selected_scenario.track_config) if selected_scenario and selected_scenario.track_config else '{}',
    }
    return render(request, 'driving_simulation/simulator.html', context)


# ══════════════════════════════════════════════════════════════
#  SAVE RESULT  – Phaser POSTs results here via AJAX
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def save_result(request):
    """
    POST /simulation/save/
    Receives JSON payload from the Phaser game with all session results.
    Updates the SimulationSession and creates CheckpointResult records.

    Expected JSON body:
    {
        "session_id": "uuid-string",
        "score": 85,
        "status": "completed",  // or "failed"
        "time_taken": 142.5,
        "total_distance": 3200,
        "max_speed": 80,
        "average_speed": 45.2,
        "collisions": 1,
        "signal_violations": 0,
        "lane_violations": 2,
        "speed_violations": 0,
        "checkpoints_cleared": 5,
        "parking_completed": false,
        "parking_accuracy": 0,
        "parking_attempts": 0,
        "checkpoints": [
            {
                "number": 1,
                "time": 25.3,
                "speed": 42,
                "penalties": 0
            },
            ...
        ],
        "telemetry": { ... }   // optional raw telemetry blob
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    session_id = data.get('session_id')
    if not session_id:
        return JsonResponse({'error': 'session_id is required.'}, status=400)

    session = get_object_or_404(
        SimulationSession,
        session_id=session_id,
        user=request.user,
    )

    # Prevent double-submission
    if session.status != 'in_progress':
        return JsonResponse(
            {'error': 'Session already finalised.'},
            status=409,
        )

    # ── Update session fields ────────────────────────
    status = data.get('status', 'completed')
    if status not in ('completed', 'failed'):
        status = 'completed'

    score = min(max(int(data.get('score', 0)), 0), 100)
    passing_score = session.scenario.passing_score if session.scenario else 60
    passed = score >= passing_score and status == 'completed'

    session.status = status
    session.score = score
    session.passed = passed
    session.time_taken_seconds = float(data.get('time_taken', 0))
    session.total_distance = float(data.get('total_distance', 0))
    session.max_speed_reached = float(data.get('max_speed', 0))
    session.average_speed = float(data.get('average_speed', 0))
    session.collision_count = int(data.get('collisions', 0))
    session.signal_violations = int(data.get('signal_violations', 0))
    session.lane_violations = int(data.get('lane_violations', 0))
    session.speed_violations = int(data.get('speed_violations', 0))
    session.checkpoints_cleared = int(data.get('checkpoints_cleared', 0))
    session.parking_completed = bool(data.get('parking_completed', False))
    session.parking_accuracy = float(data.get('parking_accuracy', 0))
    session.parking_attempts = int(data.get('parking_attempts', 0))
    session.telemetry_data = data.get('telemetry')
    session.completed_at = timezone.now()
    session.save()

    # ── Save per-checkpoint breakdown ────────────────
    checkpoints = data.get('checkpoints', [])
    checkpoint_objects = []
    for cp in checkpoints:
        checkpoint_objects.append(
            CheckpointResult(
                session=session,
                checkpoint_number=int(cp.get('number', 0)),
                time_at_checkpoint=float(cp.get('time', 0)),
                speed_at_checkpoint=float(cp.get('speed', 0)),
                penalties_at_checkpoint=int(cp.get('penalties', 0)),
            )
        )
    if checkpoint_objects:
        CheckpointResult.objects.bulk_create(checkpoint_objects)

    return JsonResponse({
        'success': True,
        'passed': passed,
        'score': score,
        'session_id': str(session.session_id),
    })


# ══════════════════════════════════════════════════════════════
#  TRIAL HISTORY  – trainee's past simulation attempts
# ══════════════════════════════════════════════════════════════

@login_required
def trial_history(request):
    """
    GET /simulation/history/
    Shows paginated history of the logged-in user's simulation attempts
    with aggregate stats.
    """
    sessions = SimulationSession.objects.filter(
        user=request.user,
    ).exclude(
        status='in_progress',
    ).select_related(
        'scenario',
    ).order_by('-started_at')

    # ── Aggregate statistics ─────────────────────────
    stats = sessions.aggregate(
        total_attempts=Count('id'),
        total_passed=Count('id', filter=Q(passed=True)),
        avg_score=Avg('score'),
        best_score=Max('score'),
        total_time=Avg('time_taken_seconds'),
        avg_collisions=Avg('collision_count'),
        avg_signal_violations=Avg('signal_violations'),
    )
    stats['pass_rate'] = (
        round((stats['total_passed'] / stats['total_attempts']) * 100, 1)
        if stats['total_attempts'] > 0 else 0
    )
    stats['avg_score'] = round(stats['avg_score'] or 0, 1)
    stats['total_time'] = round(stats['total_time'] or 0, 1)
    stats['avg_collisions'] = round(stats['avg_collisions'] or 0, 1)
    stats['avg_signal_violations'] = round(stats['avg_signal_violations'] or 0, 1)

    context = {
        'sessions': sessions,
        'stats': stats,
    }
    return render(request, 'driving_simulation/trial_history.html', context)


# ══════════════════════════════════════════════════════════════
#  SESSION DETAIL  – detailed breakdown of a single attempt
# ══════════════════════════════════════════════════════════════

@login_required
def session_detail(request, session_id):
    """
    GET /simulation/session/<uuid>/
    Detailed result view for a single simulation session, including
    per-checkpoint breakdown.
    """
    session = get_object_or_404(
        SimulationSession,
        session_id=session_id,
        user=request.user,
    )
    checkpoints = session.checkpoint_results.all()

    # Get user's best score for the same scenario for comparison
    best_session = SimulationSession.objects.filter(
        user=request.user,
        scenario=session.scenario,
        status='completed',
    ).order_by('-score').first()

    context = {
        'session': session,
        'checkpoints': checkpoints,
        'best_session': best_session,
        'is_personal_best': best_session and best_session.pk == session.pk,
    }
    return render(request, 'driving_simulation/session_detail.html', context)


# ══════════════════════════════════════════════════════════════
#  LEADERBOARD  – top scores per scenario
# ══════════════════════════════════════════════════════════════

@login_required
def leaderboard(request):
    """
    GET /simulation/leaderboard/
    Shows the top scores across all trainees, filterable by scenario.
    """
    scenario_id = request.GET.get('scenario')
    scenarios = SimulationScenario.objects.filter(is_active=True)

    top_sessions = SimulationSession.objects.filter(
        status='completed',
    ).select_related(
        'user', 'scenario',
    ).order_by('-score', 'time_taken_seconds')

    if scenario_id:
        top_sessions = top_sessions.filter(scenario_id=scenario_id)

    # Limit to top 50
    top_sessions = top_sessions[:50]

    context = {
        'scenarios': scenarios,
        'top_sessions': top_sessions,
        'selected_scenario_id': int(scenario_id) if scenario_id else None,
    }
    return render(request, 'driving_simulation/leaderboard.html', context)


# ══════════════════════════════════════════════════════════════
#  API: SCENARIO CONFIG  – Phaser fetches track config as JSON
# ══════════════════════════════════════════════════════════════

@login_required
@require_GET
def scenario_config_api(request, scenario_id):
    """
    GET /simulation/api/scenario/<id>/config/
    Returns the scenario's track_config JSON for the Phaser game to consume.
    """
    scenario = get_object_or_404(
        SimulationScenario, pk=scenario_id, is_active=True
    )
    return JsonResponse({
        'id': scenario.pk,
        'name': scenario.name,
        'scenario_type': scenario.scenario_type,
        'vehicle_type': scenario.vehicle_type,
        'difficulty': scenario.difficulty,
        'time_limit': scenario.time_limit_seconds,
        'passing_score': scenario.passing_score,
        'max_collisions': scenario.max_collisions_allowed,
        'total_checkpoints': scenario.total_checkpoints,
        'enable_traffic_signals': scenario.enable_traffic_signals,
        'enable_pedestrians': scenario.enable_pedestrians,
        'enable_weather': scenario.enable_weather,
        'enable_reverse_parking': scenario.enable_reverse_parking,
        'track_config': scenario.track_config or {},
    })


# ══════════════════════════════════════════════════════════════
#  ABANDON SESSION  – trainee quits mid-simulation
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def abandon_session(request):
    """
    POST /simulation/abandon/
    Marks an in-progress session as abandoned.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    session_id = data.get('session_id')
    if not session_id:
        return JsonResponse({'error': 'session_id required.'}, status=400)

    session = get_object_or_404(
        SimulationSession,
        session_id=session_id,
        user=request.user,
        status='in_progress',
    )
    session.status = 'abandoned'
    session.completed_at = timezone.now()
    session.save(update_fields=['status', 'completed_at'])

    return JsonResponse({'success': True})
