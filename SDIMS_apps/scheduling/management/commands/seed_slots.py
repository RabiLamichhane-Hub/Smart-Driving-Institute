from datetime import time
from django.core.management.base import BaseCommand
from SDIMS_apps.scheduling.models import TimeSlot


SLOTS = [
    (1, "Slot 1 (6–8 AM)",   time(6, 0),  time(8, 0)),
    (2, "Slot 2 (8–10 AM)",  time(8, 0),  time(10, 0)),
    (3, "Slot 3 (10–12 PM)", time(10, 0), time(12, 0)),
    (4, "Slot 4 (2–4 PM)",   time(14, 0), time(16, 0)),
    (5, "Slot 5 (4–6 PM)",   time(16, 0), time(18, 0)),
    (6, "Slot 6 (6–8 PM)",   time(18, 0), time(20, 0)),
]


class Command(BaseCommand):
    help = "Seed the 6 fixed TimeSlot rows. Safe to run multiple times."

    def handle(self, *args, **options):
        created_count = 0

        for slot_number, label, start_time, end_time in SLOTS:
            slot, created = TimeSlot.objects.get_or_create(
                slot_number=slot_number,
                defaults={
                    "label":      label,
                    "start_time": start_time,
                    "end_time":   end_time,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {slot}"))
            else:
                self.stdout.write(f"  Already exists: {slot}")

        if created_count:
            self.stdout.write(self.style.SUCCESS(
                f"\n✔ Done. {created_count} slot(s) created."
            ))
        else:
            self.stdout.write("\n✔ All slots already exist. Nothing changed.")