from django.shortcuts import render, redirect
from SDIMS_apps.courses.models import Course
from SDIMS_apps.instructors.models import Instructor
from SDIMS_apps.vehicles.models import Vehicle

def index(request):
    if request.user.is_authenticated:

        # Admin
        if request.user.is_superuser:
            return redirect('accounts:admin_dashboard')

        # Instructor
        if hasattr(request.user, 'instructor'):
            return redirect('accounts:instructor_dashboard')

        # Trainee (default fallback)
        return redirect('accounts:dashboard')

    # Not logged in → show landing page
    courses = Course.objects.all()
    instructors = Instructor.objects.select_related('user')
    vehicles = Vehicle.objects.all()

    return render(request, 'index.html', {
        'courses': courses,
        'instructors': instructors,
        'vehicles': vehicles
    })