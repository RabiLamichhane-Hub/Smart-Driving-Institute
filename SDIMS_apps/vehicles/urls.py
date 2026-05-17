from . import views
from django.urls import path

app_name = 'vehicles'

urlpatterns = [
    path('', views.vehicles_list, name='vehicles_list'),
    path('add/', views.add_vehicle, name='add_vehicle'),
    path('usage/', views.vehicle_usage, name='vehicle_usage'),
    path('edit/<int:pk>', views.vehicle_edit, name='vehicle_edit'),
]