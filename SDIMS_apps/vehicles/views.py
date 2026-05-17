from django.shortcuts import render, redirect, get_object_or_404
from .models import Vehicle
from .forms import VehicleForm
from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from SDIMS_apps.accounts.decorators import role_required

# Create your views here.
def vehicles_list(request):
    vehicles = Vehicle.objects.all()
    return render(request, 'vehicles_list.html',{'vehicles':vehicles})

def add_vehicle(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('vehicles:vehicles_list')
    else:
        form = VehicleForm()
    return render(request, 'add_vehicle.html', {'form': form})

@login_required
@role_required(['admin', 'supervisor'])
def vehicle_usage(request):
    vehicles = (
        Vehicle.objects
        .annotate(
            completed_sessions=Count(
                'sessions',
                filter=Q(sessions__status='completed'),
            ),
            booked_sessions=Count(
                'sessions',
                filter=Q(sessions__status__in=['pending', 'scheduled', 'ongoing']),
            ),
        )
        .order_by('-completed_sessions')
    )

    most_used  = vehicles.filter(completed_sessions__gt=0).first()
    least_used = vehicles.filter(completed_sessions__gt=0).last()

    return render(request, 'vehicle_usage.html', {
        'vehicles':   vehicles,
        'most_used':  most_used,
        'least_used': least_used,
    })

@login_required
@role_required(['admin', 'supervisor'])
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)

    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, f"{vehicle.brand} {vehicle.model} updated successfully.")
            return redirect('vehicles:vehicles_list',)
    else:
        form = VehicleForm(instance=vehicle)

    return render(request, 'vehicle_edit.html', {
        'form': form,
        'vehicle': vehicle,
    })