from . import views
from django.urls import path

app_name = 'courses'

urlpatterns = [
    path('', views.course_list, name='course_list'),
    path('add/', views.add_course, name='add_course'),
    path('edit/<int:pk>/', views.edit_course, name='edit_course'),
    path('ajax/vehicles/', views.ajax_vehicles_by_type, name='ajax_vehicles_by_type'),
]