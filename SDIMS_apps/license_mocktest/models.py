from django.db import models
from django.conf import settings

class Question(models.Model):
    OPTION_CHOICES = [('A','A'), ('B','B'), ('C','C'), ('D','D')]
    
    section = models.CharField(max_length=255)
    question = models.TextField()
    option_a = models.TextField()
    option_b = models.TextField()
    option_c = models.TextField()
    option_d = models.TextField()
    correct_option = models.CharField(max_length=8, choices=OPTION_CHOICES)

    def __str__(self):
        return self.question[:60]


class TestAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='test_attempts'
    )
    score = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    pass_mark = models.PositiveIntegerField(default=16)
    passed = models.BooleanField()
    taken_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.score}/{self.total} on {self.taken_at.strftime('%Y-%m-%d')}"