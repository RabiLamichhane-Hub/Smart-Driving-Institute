import pandas as pd
from django.core.management.base import BaseCommand
from SDIMS_apps.license_mocktest.models import Question  # change to your app name

OPTION_MAP = {
    "क": "A",
    "ख": "B",
    "ग": "C",
    "घ": "D"
}

class Command(BaseCommand):
    help = 'Import questions from CSV into the database'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Full path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_path = kwargs['csv_path']

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {csv_path}'))
            return

        created_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            # Skip if question already exists
            if Question.objects.filter(question=row['Question']).exists():
                skipped_count += 1
                continue

            correct = OPTION_MAP.get(
                str(row['Correct_Answer']).strip(),
                str(row['Correct_Answer']).strip()
            )

            Question.objects.create(
                section=row.get('Section', ''),
                question=row['Question'],
                option_a=row['Option_A'],
                option_b=row['Option_B'],
                option_c=row['Option_C'],
                option_d=row['Option_D'],
                correct_option=correct
            )
            created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done — {created_count} imported, {skipped_count} skipped (duplicates)'
        ))