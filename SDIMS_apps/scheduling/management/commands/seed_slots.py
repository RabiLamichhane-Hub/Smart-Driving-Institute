from datetime import time
from django.core.management.base import BaseCommand
from SDIMS_apps.scheduling.models import TimeSlot


SLOTS = [
    (1, "Slot 1 (8-9 AM)",   time(8, 0),  time(9, 0)),
    (2, "Slot 2 (9–10 AM)",  time(9, 0),  time(10, 0)),
    (3, "Slot 3 (10–11 AM)", time(10, 0), time(11, 0)),
    (4, "Slot 4 (11–12 PM)", time(11, 0), time(12, 0)),
    (5, "Slot 5 (12–1 PM)",  time(12, 0), time(13, 0)),
    (6, "Slot 6 (1–2 PM)",   time(13, 0), time(14, 0)),
    # 2–3 PM: break (no slot)
    (7, "Slot 7 (3–4 PM)",   time(15, 0), time(16, 0)),
    (8, "Slot 8 (4–5 PM)",   time(16, 0), time(17, 0)),
    (9, "Slot 9 (5-6 PM)",  time (17,0), time(18, 0)),
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
                # Update in case times/labels changed (e.g. switched to 1-hour slots)
                updated_fields = []
                if slot.label != label:
                    slot.label = label
                    updated_fields.append('label')
                if slot.start_time != start_time:
                    slot.start_time = start_time
                    updated_fields.append('start_time')
                if slot.end_time != end_time:
                    slot.end_time = end_time
                    updated_fields.append('end_time')

                if updated_fields:
                    slot.save(update_fields=updated_fields)
                    self.stdout.write(self.style.WARNING(
                        f"  Updated: {slot} (fields: {', '.join(updated_fields)})"
                    ))
                else:
                    self.stdout.write(f"  Already exists: {slot}")

        if created_count:
            self.stdout.write(self.style.SUCCESS(
                f"\n✔ Done. {created_count} slot(s) created."
            ))
        else:
            self.stdout.write("\n✔ All slots processed. Nothing created.")