# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from SDIMS_apps.trainees.models import Trainee
from .models import FeeRecord, Expense
from .forms import PaymentForm, ExpenseForm


@login_required
def add_payment(request, pk):
    trainee = get_object_or_404(Trainee, pk=pk)

    fee_record, created = FeeRecord.objects.get_or_create(
        trainee=trainee,
        defaults={
            'course': trainee.course,
            'total_fee': trainee.course.fee if trainee.course else 0
        }
    )

    form = PaymentForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            payment = form.save(commit=False)
            payment.fee_record = fee_record
            payment.received_by = request.user

            try:
                payment.save()
                messages.success(request, "Payment recorded successfully.")
                return redirect('trainees:trainee_detail', trainee_id=trainee.pk)
            except ValidationError as e:
                messages.error(request, e.message)
            except Exception as e:
                messages.error(request, f"Unexpected error: {e}")
                return redirect('accounting:fee_overview')

    context = {
        'form': form,
        'trainee': trainee,
        'fee_record': fee_record,
        'paid': fee_record.total_paid(),
        'remaining': fee_record.remaining(),
    }
    return render(request, 'add_payment.html', context)


@login_required
def add_expense(request):
    form = ExpenseForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            expense = form.save(commit=False)
            expense.recorded_by = request.user

            try:
                expense.save()
                messages.success(request, "Expense recorded successfully.")
                return redirect('accounting:expense_list')
            except ValidationError as e:
                messages.error(request, e.message)
            except Exception as e:
                messages.error(request, f"Unexpected error: {e}")

    context = {
        'form': form,
    }
    return render(request, 'add_expense.html', context)


@login_required
def expense_list(request):
    expenses = Expense.objects.select_related('recorded_by').all()

    context = {
        'expenses': expenses,
    }
    return render(request, 'expense_list.html', context)


@login_required
def fee_overview(request):
    fee_records = FeeRecord.objects.select_related(
        'trainee', 'course'
    ).prefetch_related('payments').all()

    context = {
        'fee_records': fee_records,
    }
    return render(request, 'fee_overview.html', context)