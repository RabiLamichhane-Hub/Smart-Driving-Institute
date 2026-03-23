from django.shortcuts import render, get_object_or_404, redirect
from .models import Instructor
from .forms import InstructorForm

# List all instructors
def instructor_list(request):
    instructors = Instructor.objects.all()
    return render(request, 'instructor_list.html', {'instructors': instructors})

# Add new instructor
def instructor_create(request):
    if request.method == 'POST':
        form = InstructorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('instructors:instructor_list')
    else:
        form = InstructorForm()
    return render(request, 'instructor_form.html', {'form': form})

# Edit existing instructor
def instructor_update(request, pk):
    instructor = get_object_or_404(Instructor, pk=pk)
    if request.method == 'POST':
        form = InstructorForm(request.POST, instance=instructor)
        if form.is_valid():
            form.save()
            return redirect('instructors:instructor_list')
    else:
        form = InstructorForm(instance=instructor)
    return render(request, 'instructor_form.html', {'form': form})

# Delete instructor
def instructor_delete(request, pk):
    instructor = get_object_or_404(Instructor, pk=pk)
    if request.method == 'POST':
        instructor.delete()
        return redirect('instructors:instructor_list')
    return render(request, 'instructor_confirm_delete.html', {'instructor': instructor})