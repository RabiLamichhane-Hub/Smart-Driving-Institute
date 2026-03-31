from django.shortcuts import render, redirect
from .utils import generate_random_mocktest

def mocktest(request):
    if request.method != "GET":
        return redirect('license_mocktest:mocktest')

    mocktest_data = generate_random_mocktest()  # no argument needed
    request.session['mocktest_data'] = mocktest_data

    return render(request, "mocktest.html", {"mocktest": mocktest_data})


def result(request):
    if request.method == "POST":
        mocktest_data = request.session.get('mocktest_data', [])

        if not mocktest_data:
            return redirect('license_mocktest:mocktest')

        score = 0
        result_list = []

        for q in mocktest_data:
            selected = request.POST.get(str(q['id']))
            correct_full = q['answer']  # e.g. "Option_B"

            # Extract correct option letter
            correct = correct_full.split("_")[-1]  # "B"

            # Normalize selected
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

        # Store result with details
        request.session['result'] = {
            'score': score,
            'total': len(mocktest_data),
            'pass_mark': 16,
            'details': result_list   # 🔥 added
        }

        del request.session['mocktest_data']
        return redirect('license_mocktest:mocktest_result')

    # GET — show stored result
    result_data = request.session.pop('result', None)
    if not result_data:
        return redirect('license_mocktest:mocktest')

    return render(request, "result.html", result_data)