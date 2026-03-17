from django.shortcuts import render, redirect
from .forms import StudentForm

# Create your views here.
def register(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('student_list')
    else:
        form = StudentForm()
    return render(request, 'register.html', {'form': form})