from . import views
from django.urls import path

app_name = 'vehicles'

urlpatterns = [
    path('', views.vehicles_list, name='vehicles_list'),
]