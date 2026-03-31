from django.db import models

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