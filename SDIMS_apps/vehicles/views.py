from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q

from .models import Vehicle
from .forms import VehicleForm
from SDIMS_apps.accounts.decorators import role_required


# ─────────────────────────────────────────────
# Shared permission shorthand
# ─────────────────────────────────────────────
ADMIN_SUPERVISOR = ['admin', 'supervisor']


# ─────────────────────────────────────────────
# Vehicles list
# ─────────────────────────────────────────────
@login_required
def vehicles_list(request):
    """
    Display all vehicles with lightweight status-based filtering.
    Query param: ?status=available|maintenance|inactive
    """
    status_filter = request.GET.get('status', '').strip()

    vehicles = Vehicle.objects.all()
    if status_filter:
        vehicles = vehicles.filter(status=status_filter)

    context = {
        'vehicles': vehicles,
        'active_filter': status_filter,
    }
    return render(request, 'vehicles_list.html', context)


# ─────────────────────────────────────────────
# Add vehicle
# ─────────────────────────────────────────────
@login_required
@role_required(ADMIN_SUPERVISOR)
def add_vehicle(request):
    """Create a new vehicle record."""
    form = VehicleForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if form.is_valid():
            vehicle = form.save()
            messages.success(
                request,
                f"{vehicle.brand} {vehicle.model} added to the fleet."
            )
            return redirect('vehicles:vehicles_list')
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, 'add_vehicle.html', {'form': form})


# ─────────────────────────────────────────────
# Edit vehicle
# ─────────────────────────────────────────────
@login_required
@role_required(ADMIN_SUPERVISOR)
def vehicle_edit(request, pk):
    """Update an existing vehicle record."""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    form = VehicleForm(
        request.POST or None,
        request.FILES or None,
        instance=vehicle,
    )

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"{vehicle.brand} {vehicle.model} updated successfully."
            )
            return redirect('vehicles:vehicles_list')
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, 'vehicle_edit.html', {
        'form': form,
        'vehicle': vehicle,
    })


# ─────────────────────────────────────────────
# Delete vehicle
# ─────────────────────────────────────────────
@login_required
@role_required(['admin'])
def vehicle_delete(request, pk):
    """
    Delete a vehicle. Only admins can delete.
    GET  → renders a confirmation page.
    POST → performs the delete and redirects to the list.
    """
    vehicle = get_object_or_404(Vehicle, pk=pk)

    if request.method == 'POST':
        label = f"{vehicle.brand} {vehicle.model}"
        vehicle.delete()
        messages.success(request, f"{label} has been removed from the fleet.")
        return redirect('vehicles:vehicles_list')

    # GET → show confirmation page
    return render(request, 'vehicle_delete.html', {'vehicle': vehicle})


# ─────────────────────────────────────────────
# Vehicle usage stats
# ─────────────────────────────────────────────
@login_required
@role_required(ADMIN_SUPERVISOR)
def vehicle_usage(request):
    """
    Annotate each vehicle with completed and active session counts,
    then surface the most- and least-used vehicles.
    """
    ACTIVE_STATUSES = ['pending', 'scheduled', 'ongoing']

    vehicles = (
        Vehicle.objects
        .annotate(
            completed_sessions=Count(
                'sessions',
                filter=Q(sessions__status='completed'),
            ),
            booked_sessions=Count(
                'sessions',
                filter=Q(sessions__status__in=ACTIVE_STATUSES),
            ),
        )
        .order_by('-completed_sessions')
    )

    used_vehicles = vehicles.filter(completed_sessions__gt=0)
    most_used  = used_vehicles.first()
    least_used = used_vehicles.last()

    # Prevent most_used == least_used when only one vehicle has sessions
    if most_used and least_used and most_used.pk == least_used.pk:
        least_used = None

    return render(request, 'vehicle_usage.html', {
        'vehicles':   vehicles,
        'most_used':  most_used,
        'least_used': least_used,
    })