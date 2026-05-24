"""
management/commands/diagnose_public_slots.py

Run with:
    python manage.py diagnose_public_slots

Prints a step-by-step breakdown of the public vacancy calculation so you can
see exactly where the chain is breaking and why the slot grid is empty.
"""

from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Diagnose why public walk-in slots are not showing on the landing page."

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("  PUBLIC SLOT VACANCY DIAGNOSTIC")
        self.stdout.write("=" * 60 + "\n")

        # ── Step 1: SchedulingConfig ── #
        from SDIMS_apps.scheduling.models import SchedulingConfig
        config = SchedulingConfig.load()

        self.stdout.write("── SchedulingConfig ──")
        self.stdout.write(f"  public_booking_enabled     : {config.public_booking_enabled}")
        self.stdout.write(f"  public_booking_cutoff_hours: {config.public_booking_cutoff_hours}")
        self.stdout.write(f"  course_capacity_pct        : {config.course_capacity_pct}")
        self.stdout.write(f"  public_session_fee         : {config.public_session_fee}")

        if not config.public_booking_enabled:
            self.stdout.write(
                self.style.ERROR(
                    "\n  ✗ BOOKING IS DISABLED — set public_booking_enabled=True in Django admin."
                )
            )
            return
        self.stdout.write(self.style.SUCCESS("  ✓ Booking is enabled.\n"))

        # ── Step 2: Resources ── #
        from SDIMS_apps.vehicles.models import Vehicle
        from SDIMS_apps.instructors.models import Instructor
        from SDIMS_apps.scheduling.models import Track, TimeSlot

        car_vehicles = Vehicle.objects.filter(status='available', vehicle_type='car').count()
        tw_vehicles  = Vehicle.objects.filter(status='available', vehicle_type__in=('bike', 'scooter')).count()
        all_vehicles = Vehicle.objects.count()
        all_avail    = Vehicle.objects.filter(status='available').count()

        car_tracks = Track.objects.filter(status='active', track_type='car').count()
        tw_tracks  = Track.objects.filter(status='active', track_type='two_wheeler').count()
        all_tracks = Track.objects.count()

        instructors       = Instructor.objects.filter(status='active').count()
        all_instructors   = Instructor.objects.count()

        slots_count = TimeSlot.objects.count()

        self.stdout.write("── Resources ──")
        self.stdout.write(f"  TimeSlots seeded           : {slots_count}  (need > 0)")
        self.stdout.write(f"  Vehicles total / available : {all_vehicles} / {all_avail}")
        self.stdout.write(f"    → available cars         : {car_vehicles}")
        self.stdout.write(f"    → available 2-wheelers   : {tw_vehicles}")
        self.stdout.write(f"  Tracks total               : {all_tracks}")
        self.stdout.write(f"    → active car tracks      : {car_tracks}")
        self.stdout.write(f"    → active 2-wheeler tracks: {tw_tracks}")
        self.stdout.write(f"  Active instructors         : {instructors} / {all_instructors}")

        if slots_count == 0:
            self.stdout.write(
                self.style.ERROR(
                    "\n  ✗ NO TIMESLOTS — run: python manage.py seed_slots"
                )
            )
            return

        # ── Step 3: Capacity maths ── #
        pct = config.course_capacity_pct

        def _indep(track_cnt, vehicle_cnt, inst_cnt):
            track_cap    = track_cnt * 2
            guided_total = min(track_cap, vehicle_cnt, inst_cnt)
            unguided     = min(track_cap, vehicle_cnt)
            reserved     = int(guided_total * pct) if guided_total > 0 else 0
            base         = max(0, unguided - reserved)
            return track_cap, guided_total, unguided, reserved, base

        self.stdout.write("\n── Capacity calculation (using int/floor, not round) ──")

        ct, cg, cu, cr, cb = _indep(car_tracks, car_vehicles, instructors)
        self.stdout.write("  4-Wheeler (car):")
        self.stdout.write(f"    track_capacity  = {car_tracks} × 2 = {ct}")
        self.stdout.write(f"    guided_total    = min({ct}, {car_vehicles} vehicles, {instructors} instructors) = {cg}")
        self.stdout.write(f"    unguided_total  = min({ct}, {car_vehicles}) = {cu}")
        self.stdout.write(f"    course_reserved = int({cg} × {pct}) = {cr}")
        self.stdout.write(f"    car_base        = max(0, {cu} - {cr}) = {cb}")
        if cb == 0:
            self.stdout.write(self.style.WARNING("    ⚠ car_base=0 — no 4-wheeler independent slots."))
        else:
            self.stdout.write(self.style.SUCCESS(f"    ✓ car_base={cb}"))

        tt, tg, tu, tr, tb = _indep(tw_tracks, tw_vehicles, instructors)
        self.stdout.write("  2-Wheeler (bike/scooter):")
        self.stdout.write(f"    track_capacity  = {tw_tracks} × 2 = {tt}")
        self.stdout.write(f"    guided_total    = min({tt}, {tw_vehicles} vehicles, {instructors} instructors) = {tg}")
        self.stdout.write(f"    unguided_total  = min({tt}, {tw_vehicles}) = {tu}")
        self.stdout.write(f"    course_reserved = int({tg} × {pct}) = {tr}")
        self.stdout.write(f"    tw_base         = max(0, {tu} - {tr}) = {tb}")
        if tb == 0:
            self.stdout.write(self.style.WARNING("    ⚠ tw_base=0 — no 2-wheeler independent slots."))
        else:
            self.stdout.write(self.style.SUCCESS(f"    ✓ tw_base={tb}"))

        if cb == 0 and tb == 0:
            self.stdout.write(
                self.style.ERROR(
                    "\n  ✗ BOTH BASES ARE ZERO — nothing to display.\n"
                    "  Fix options (any one is enough):\n"
                    "    A) Add more available vehicles of the relevant type.\n"
                    "    B) Add / activate a track of the relevant type.\n"
                    "    C) Lower course_capacity_pct (e.g. 0.50 instead of 0.70)."
                )
            )
            return

        # ── Step 4: Cutoff check against working days ── #
        from SDIMS_apps.scheduling.scheduler import is_working_day

        now   = datetime.now()
        check = date.today()
        days  = []
        while len(days) < 8:
            if is_working_day(check):
                days.append(check)
            check += timedelta(days=1)

        self.stdout.write(f"\n── Cutoff check (cutoff_hours={config.public_booking_cutoff_hours}, now={now.strftime('%H:%M')}) ──")

        slots = list(TimeSlot.objects.order_by('slot_number'))
        visible_days = 0

        for d in days:
            visible_slots = []
            for s in slots:
                slot_start  = datetime.combine(d, s.start_time)
                hours_until = (slot_start - now).total_seconds() / 3600
                if hours_until >= config.public_booking_cutoff_hours:
                    visible_slots.append(f"{s.label} (+{hours_until:.1f}h)")
            if visible_slots:
                self.stdout.write(
                    self.style.SUCCESS(f"  {d.strftime('%a %d %b')} — {len(visible_slots)} slot(s) pass cutoff:")
                )
                for sl in visible_slots:
                    self.stdout.write(f"      {sl}")
                visible_days += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f"  {d.strftime('%a %d %b')} — ALL slots within cutoff, day hidden.")
                )

        if visible_days == 0:
            self.stdout.write(
                self.style.ERROR(
                    "\n  ✗ NO DAYS PASS THE CUTOFF.\n"
                    f"  All slots for the next 8 working days are within {config.public_booking_cutoff_hours}h.\n"
                    "  Fix: lower public_booking_cutoff_hours in Django admin (e.g. 2 or 6)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n  ✓ {visible_days} day(s) have visible slots.")
            )

        self.stdout.write("\n" + "=" * 60 + "\n")