from . import views
from django.urls import path

app_name = 'trainees'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('list/', views.trainee_list, name='trainee_list'),
]