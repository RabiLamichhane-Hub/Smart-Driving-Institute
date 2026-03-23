from django.urls import path
from . import views

app_name = 'instructors'

urlpatterns = [
    path('', views.instructor_list, name='instructor_list'),
    path('add/', views.instructor_create, name='instructor_create'),
    path('edit/<int:pk>/', views.instructor_update, name='instructor_update'),
    path('delete/<int:pk>/', views.instructor_delete, name='instructor_delete'),
]