from . import views
from django.urls import path

app_name = 'license_mocktest'

urlpatterns = [
    path('', views.mocktest, name='mocktest'),
    path('result/', views.result, name='mocktest_result'),
]