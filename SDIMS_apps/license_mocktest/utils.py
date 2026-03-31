import random
from .models import Question

def generate_random_mocktest(num_questions=25):
    questions = list(Question.objects.all())

    if not questions:
        return []

    selected = random.sample(questions, min(num_questions, len(questions)))

    mocktest_list = []
    for q in selected:
        mocktest_list.append({
            "id": q.id,
            "question": q.question,
            "options": {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d,
            },
            "answer": q.correct_option
        })

    return mocktest_list