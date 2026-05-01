from django.urls import path
from . import views

app_name = 'scheduling'

urlpatterns = [
    # Trainee
    path('preferences/', views.TraineePreferenceView.as_view(), name='preferences'),
    path('my-schedule/', views.my_schedule_view, name='my_schedule'),

    # Supervisor / Admin — sessions
    path('sessions/', views.session_list_view, name='session_list'),
    path('approve/', views.approve_schedule_view, name='approve'),
    path('approve/<int:pk>/', views.approve_single_session_view, name='approve_single'),
    path('cancel/<int:pk>/', views.cancel_session_view, name='cancel_session'),

    # Supervisor / Admin — attendance
    path('attendance/today/', views.attendance_today_view, name='attendance_today'),
    path('attendance/history/', views.attendance_history_view, name='attendance_history'),

    # Supervisor / Admin — reschedule
    path('reschedule/queue/', views.reschedule_queue_view, name='reschedule_queue'),
    path('reschedule/flagged/', views.flagged_reschedule_view, name='flagged_reschedule'),

    # Scheduler control
    path('run-scheduler/', views.run_scheduler_view, name='run_scheduler'),
    path('run-scheduler/bulk/', views.run_scheduler_bulk_view, name='run_scheduler_bulk'),
    path('runs/', views.schedule_run_list_view, name='run_list'),
    path('runs/<int:pk>/', views.schedule_run_detail_view, name='run_detail'),
]