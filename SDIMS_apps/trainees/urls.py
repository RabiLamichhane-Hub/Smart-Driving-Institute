from . import views
from django.urls import path

app_name = 'trainees'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('list/', views.trainee_list, name='trainee_list'),
    path('edit/<int:pk>/', views.trainee_edit, name='trainee_edit'),
    path('delete/<int:pk>/', views.trainee_delete, name='trainee_delete'),
    path('details/<int:pk>/', views.details, name='details'),
    path('ajax/course-fee/', views.ajax_course_fee, name='ajax_course_fee'),
]