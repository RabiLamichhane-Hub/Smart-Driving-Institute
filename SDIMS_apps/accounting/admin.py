from django.contrib import admin
from .models import Expense, Payment, FeeRecord, SessionPayment

# Register your models here.

admin.site.register(FeeRecord)
admin.site.register(Expense)
admin.site.register(Payment)


@admin.register(SessionPayment)
class SessionPaymentAdmin(admin.ModelAdmin):
    list_display  = ('public_booking', 'amount', 'method', 'received_by', 'date')
    list_filter   = ('method', 'date')
    search_fields = ('public_booking__guest_name', 'public_booking__guest_phone')