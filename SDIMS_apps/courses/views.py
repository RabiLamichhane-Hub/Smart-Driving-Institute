from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from SDIMS_apps.accounts.decorators import admin_required
from SDIMS_apps.vehicles.models import Vehicle
from .forms import CourseForm
from .models import Course
from django.contrib import messages
from django.http import JsonResponse

@login_required
@admin_required
def add_course(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)

        if form.is_valid():
            form.save()  
            messages.success(request, "Course added successfully!")
            return redirect('courses:course_list')

        else:
            messages.error(request, "Please fix the errors below.")

    else:
        form = CourseForm()

    return render(request, 'addcourse.html', {'form': form})

@login_required
@admin_required
def edit_course(request, pk):
    course = Course.objects.get(pk=pk)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            return redirect('courses:course_list')
    else:
        form = CourseForm(instance=course)
    return render(request, 'addcourse.html', {'form': form})

def course_list(request):
    courses = Course.objects.all()

    return render(request, 'course_list.html', {
        'courses': courses
    })

def ajax_vehicles_by_type(request):
    vehicle_type = request.GET.get('vehicle_type')
    vehicles = Vehicle.objects.filter(vehicle_type=vehicle_type)
    data = {
        'vehicles': [{'id': v.id, 'brand': v.brand, 'model': v.model, 'registration_number': v.registration_number} for v in vehicles]
    }
    return JsonResponse(data)