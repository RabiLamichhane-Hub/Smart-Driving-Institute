from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from SDIMS_apps.accounts.decorators import role_required
from .forms import CourseForm
from .models import Course

@login_required
@role_required(['admin'])
def add_course(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('courses:course_list')
    else:
        form = CourseForm()
    return render(request, 'addcourse.html', {'form': form})


@login_required
@role_required(['admin'])
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