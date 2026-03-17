from . import views
from django.urls import path

app_name = 'students'

urlpatterns = [
    path('register_new/', views.register, name='register'),
]