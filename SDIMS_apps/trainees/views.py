from django.shortcuts import render, redirect
from .forms import TraineeForm
from .models import Trainee

# Create your views here.
def register(request):
    if request.method == 'POST':
        form = TraineeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('trainees:trainee_list')
    else:
        form = TraineeForm()
    return render(request, 'register.html', {'form': form})

def trainee_list(request):
    trainees = Trainee.objects.all().order_by('first_name')

    context = {
        'trainees': trainees
    }
    return render(request, 'trainee_list.html', context)