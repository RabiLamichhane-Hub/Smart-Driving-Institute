from django.contrib import admin
from .models import Expense, Payment, FeeRecord

# Register your models here.

admin.site.register(FeeRecord)
admin.site.register(Expense)
admin.site.register(Payment)