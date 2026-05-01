from . import views
from django.urls import path

app_name = 'homesandall'

urlpatterns = [
    path('', views.index, name='index'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('instructor-dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    path('dashboard/', views.trainee_dashboard, name='trainee_dashboard'),
]