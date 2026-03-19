from django.urls import path
from .views import CustomLoginView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('redirect/', views.redirect_user, name='redirect_user'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('instructor-dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    path('trainee-dashboard/', views.trainee_dashboard, name='trainee_dashboard'),
]