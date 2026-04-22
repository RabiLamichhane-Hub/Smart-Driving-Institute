from django.shortcuts import render, redirect
from .utils import generate_random_mocktest
from django.contrib.auth.decorators import login_required
from .models import TestAttempt

def mocktest(request):
    if request.method != "GET":
        return redirect('license_mocktest:mocktest')

    # If test already in progress, reuse it — don't generate new ones
    mocktest_data = request.session.get('mocktest_data')

    if not mocktest_data:
        mocktest_data = generate_random_mocktest()
        request.session['mocktest_data'] = mocktest_data

    return render(request, "mocktest.html", {"mocktest": mocktest_data})

def new_mocktest(request):
    # Clear existing session data and start fresh
    if 'mocktest_data' in request.session:
        del request.session['mocktest_data']
    return redirect('license_mocktest:mocktest')

@login_required
def result(request):
    if request.method == "POST":
        mocktest_data = request.session.get('mocktest_data', [])

        if not mocktest_data:
            return redirect('license_mocktest:mocktest')

        score = 0
        result_list = []

        for q in mocktest_data:
            selected = request.POST.get(str(q['id']))
            correct = q['answer'].strip().split('_')[-1].upper()
            selected_clean = selected.strip().upper() if selected else None
            is_correct = selected_clean == correct

            if is_correct:
                score += 1

            result_list.append({
                "question": q['question'],
                "options": q['options'],
                "selected": selected_clean,
                "correct": correct,
                "is_correct": is_correct
            })

        passed = score >= 16

        # Save attempt to database
        TestAttempt.objects.create(
            user=request.user,
            score=score,
            total=len(mocktest_data),
            pass_mark=16,
            passed=passed,
        )

        request.session['result'] = {
            'score': score,
            'total': len(mocktest_data),
            'pass_mark': 16,
            'passed': passed,
            'details': result_list,
        }

        del request.session['mocktest_data']
        return redirect('license_mocktest:mocktest_result')

    result_data = request.session.pop('result', None)
    if not result_data:
        return redirect('license_mocktest:mocktest')

    return render(request, "result.html", {'result': result_data})

@login_required
def test_history(request):
    attempts = TestAttempt.objects.filter(
        user=request.user
    ).order_by('-taken_at')

    return render(request, 'test_history.html', {'attempts': attempts})