from django.shortcuts import render, get_object_or_404, redirect
from .models import TrainingSession
from .forms import TrainingSessionForm

# LIST
def session_list(request):
    sessions = TrainingSession.objects.all()
    return render(request, 'session_list.html', {'sessions': sessions})

# CREATE
def session_create(request):
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('training:session_list')
    else:
        form = TrainingSessionForm()
    return render(request, 'session_form.html', {'form': form})

# UPDATE
def session_update(request, pk):
    session = get_object_or_404(TrainingSession, pk=pk)
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            return redirect('training:session_list')
    else:
        form = TrainingSessionForm(instance=session)
    return render(request, 'session_form.html', {'form': form})

# DELETE
def session_delete(request, pk):
    session = get_object_or_404(TrainingSession, pk=pk)
    if request.method == 'POST':
        session.delete()
        return redirect('training:session_list')
    return render(request, 'session_confirm_delete.html', {'session': session})