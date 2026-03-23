from django.shortcuts import render, redirect
from .models import Vehicle
from .forms import VehicleForm

# Create your views here.
def vehicles_list(request):
    vehicles = Vehicle.objects.all()
    return render(request, 'vehicles_list.html',{'vehicles':vehicles})

def add_vehicle(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid:
            form.save()
            return redirect('vehicles:vehicles_list')
    else:
        form = VehicleForm
    return render(request, 'add_vehicle.html', {'form':form})