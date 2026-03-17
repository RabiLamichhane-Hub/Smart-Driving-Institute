from . import views
from django.urls import path

app_name = 'students'

urlpatterns = [
    path('', views.register, name='register'),
]