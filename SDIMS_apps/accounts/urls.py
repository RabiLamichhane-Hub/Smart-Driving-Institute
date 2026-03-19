from django.urls import path
from .views import CustomLoginView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('redirect/', views.redirect_user, name='redirect_user'),
]