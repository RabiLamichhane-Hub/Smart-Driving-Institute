from django.shortcuts import render
from .models import Vehicle

# Create your views here.
def vehicles_list(request):
    vehicles = Vehicle.objects.all()
    return render(request, 'vehicles_list.html',{'vehicles':vehicles})