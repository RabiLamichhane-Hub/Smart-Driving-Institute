import datetime
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('trainees', '0001_initial'),
        ('courses', '0002_course_vehicles'),  # make sure courses migration exists
    ]

    operations = [
        migrations.AddField(
            model_name='trainee',
            name='enrollment_date',
            field=models.DateField(auto_now_add=True, default=datetime.date.today),
            preserve_default=False,
        ),
    ]