from . import views
from django.urls import path

app_name = 'license_mocktest'

urlpatterns = [
    path('', views.mocktest, name='mocktest'),
    path('result/', views.result, name='mocktest_result'),
    path('new/', views.new_mocktest, name='new_mocktest'),
    path('history/', views.test_history, name='test_history'),
]