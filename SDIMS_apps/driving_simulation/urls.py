from . import views
from django.urls import path

app_name = 'driving_simulation'

urlpatterns = [
    # ── Simulator page (scenario picker + Phaser game) ──
    path('', views.simulator, name='simulator'),

    # ── AJAX endpoints (called by Phaser JS) ────────────
    path('save/', views.save_result, name='save_result'),
    path('abandon/', views.abandon_session, name='abandon_session'),

    # ── API for Phaser to fetch scenario config ─────────
    path('api/scenario/<int:scenario_id>/config/', views.scenario_config_api, name='scenario_config_api'),

    # ── History & detail views ──────────────────────────
    path('history/', views.trial_history, name='trial_history'),
    path('session/<uuid:session_id>/', views.session_detail, name='session_detail'),

    # ── Leaderboard ─────────────────────────────────────
    path('leaderboard/', views.leaderboard, name='leaderboard'),
]