# urls.py
from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('add_payment/<int:pk>/', views.add_payment, name='add_payment'),
    path('add-expense/', views.add_expense, name='add_expense'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('', views.fee_overview, name='fee_overview'),
]