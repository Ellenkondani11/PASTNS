import random
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework.authtoken.models import Token
from core.models import Applicant, Application, Notification, Office, Profile, SmsTemplate, Stage, StageChange
from core.services import render_message


STAGES = [
    ("received", 10, "Received", "Your application is registered. Keep your tracking code. Do not travel yet.", "Fomu yanu yalembetsedwa. Sungani tracking code. Musapite ku ofesi panobe.", "grey", True, False),
    ("under_review", 20, "Under review", "Your documents are being checked. Do not travel yet.", "Zikalata zanu zikuwunikidwa. Musapite ku ofesi panobe.", "blue", True, False),
    ("approved", 30, "Approved", "Your application is approved and being prepared. Do not travel yet.", "Pempho lanu lavomerezedwa ndipo likukonzedwa. Musapite panobe.", "green", True, False),
    ("printed", 40, "Printed", "Your passport is printed and being sent to Mangochi. Do not travel yet.", "Pasipoti yasindikizidwa ndipo ikubwera ku Mangochi. Musapite panobe.", "teal", True, False),
    ("ready", 50, "Ready for collection", "Your passport is ready. Bring your National ID to Mangochi office.", "Pasipoti yanu yakonzeka. Bwerani ndi ID yanu ku ofesi ya Mangochi.", "amber", True, False),
    ("collected", 60, "Collected", "Your passport has been collected. Keep it safe.", "Pasipoti yanu yatengedwa. Isungeni bwino.", "dark", False, True),
    ("on_hold", 70, "On hold", "Your application needs attention. Contact Mangochi office before travelling.", "Pempho lanu likufunika chisamaliro. Lumikizanani ndi ofesi musanapite.", "red", True, False),
    ("rejected", 80, "Rejected", "Your application needs follow-up. Contact Mangochi office for information.", "Pempho lanu likufunika kutsatira. Lumikizanani ndi ofesi ya Mangochi.", "red", True, True),
]
TEMPLATES = [
    ("received", "Received", "Immigration: {code} received at {office}. Check *384*123#. Keep this code.", "Immigration: fomu {code} yalandiridwa ku {office}. Fufuzani *384*123#. Sungani code."),
    ("under_review", "Under review", "Immigration: {code} is under review. Do not travel yet. Check *384*123#.", "Immigration: {code} ikuwunikidwa. Musapite panobe. Fufuzani *384*123#."),
    ("approved", "Approved", "Immigration: {code} approved. It is being prepared. Do not travel yet. *384*123#.", "Immigration: {code} yavomerezedwa. Ikukonzedwa; musapite panobe. *384*123#."),
    ("printed", "Printed", "Immigration: {code} printed and on its way to {office}. Do not travel yet. *384*123#.", "Immigration: {code} yasindikizidwa, ikubwera ku {office}. Musapite panobe. *384*123#."),
    ("ready", "Ready for collection", "Immigration: passport {code} READY at {office}. Bring your National ID. Mon-Fri 8-16.", "Immigration: pasipoti {code} YAKONZEKA ku {office}. Bwerani ndi ID. Lolemba-Lachisanu 8-16."),
    ("collected", "Collected", "Immigration: {code} marked collected. Thank you.", "Immigration: {code} yalembedwa kuti mwatenga. Zikomo."),
    ("on_hold", "On hold", "Immigration: {code} is on hold. Contact {office} before travelling.", "Immigration: {code} yayimitsidwa. Lumikizanani ndi {office} musanapite."),
    ("rejected", "Rejected", "Immigration: {code} needs follow-up. Contact {office} for information.", "Immigration: {code} ikufunika kutsatira. Funsani ku {office}."),
]
FIRST_NAMES = ["Chisomo", "Thoko", "Blessings", "Tadala", "Memory", "Yamikani", "Chimwemwe", "Mphatso", "Grace", "Peter", "Loveness", "Gift", "Agnes", "Dalitso", "Fyness", "Patricia", "Victor", "Chifundo", "John", "Esnart", "Ruth", "James", "Tionge", "Madalitso"]
SURNAMES = ["Banda", "Phiri", "Chirwa", "Mbewe", "Zimba", "Kachale", "Chimangeni", "Nkhoma", "Jere", "Mvula", "Kondowe", "Mkandawire", "Nyirenda", "Kalua", "Chisale", "Lungu", "Moyo", "Kazembe", "Mhone", "Kamanga"]

class Command(BaseCommand):
    help = "Create one Mangochi office and realistic sample users/applications for the PASTNS demo."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete demo applications and applicants before seeding.")

    def handle(self, *args, **options):
        random.seed(617)
        office, _ = Office.objects.update_or_create(code="MGC", defaults={
            "name": "Mangochi Immigration Office", "district": "Mangochi", "phone": "+265 1 594 300",
            "address": "Immigration Office, along the Mangochi–Monkey Bay Road, Mangochi",
            "collection_hours": "Monday–Friday, 08:00–16:00",
            "collection_hours_ny": "Lolemba–Lachisanu, 08:00–16:00",
        })
        stage_map = {}
        for key, order, name, en, ny, colour, notify, terminal in STAGES:
            stage_map[key], _ = Stage.objects.update_or_create(key=key, defaults={
                "order": order, "name": name, "applicant_text_en": en, "applicant_text_ny": ny,
                "colour": colour, "notify": notify, "is_terminal": terminal,
            })
        for key, name, en, ny in TEMPLATES:
            SmsTemplate.objects.update_or_create(key=key, defaults={"name": name, "body_en": en, "body_ny": ny, "is_active": True})
        credentials = [("officer", "officer123", "officer"), ("supervisor", "super123", "supervisor"), ("admin", "admin123", "admin")]
        users = {}
        for username, password, role in credentials:
            user, created = User.objects.get_or_create(username=username, defaults={"first_name": username.title(), "is_staff": True, "is_active": True})
            user.is_staff = True
            user.is_active = True
            user.set_password(password)
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role, profile.office = role, office
            profile.save()
            Token.objects.get_or_create(user=user)
            users[role] = user
        if options["reset"]:
            Application.objects.all().delete()
            Applicant.objects.filter(applications__isnull=True).delete()
        existing = Application.objects.filter(office=office).count()
        now = timezone.now()
        desired = [12, 30, 24, 12, 26, 12, 3, 1]
        stage_keys = [row[0] for row in STAGES]
        created_count = 0
        # Each target stage follows a plausible, complete path through the workflow.
        for i in range(existing + 1, 121):
            target_key = stage_keys[(i - 1) % len(stage_keys)]
            # Distribute exactly by stage buckets (received, review, approved, printed, ready, collected, hold, rejected).
            cumulative = 0
            for key, count in zip(stage_keys, desired):
                cumulative += count
                if i <= cumulative:
                    target_key = key
                    break
            suffix = i
            national_id = f"{suffix:013d}"
            first, surname = FIRST_NAMES[(i * 7) % len(FIRST_NAMES)], SURNAMES[(i * 11) % len(SURNAMES)]
            phone_prefix = "+26599" if i % 2 else "+26588"
            phone = phone_prefix + f"{(7654321 + i * 7919) % 10000000:07d}"
            applicant, _ = Applicant.objects.get_or_create(national_id=national_id, defaults={
                "first_name": first, "surname": surname, "phone": phone,
                "email": f"{first.lower()}.{surname.lower()}{i}@example.mw" if i % 4 == 0 else "",
                "language": "ny" if i % 2 == 0 else "en",
            })
            code = f"MW-MGC-{now.year}-{i:05d}"
            if Application.objects.filter(tracking_code=code).exists():
                continue
            received_at = now - timedelta(days=random.randint(10, 150), hours=random.randint(0, 23))
            target_order = stage_map[target_key].order
            active_path = [stage_map[key] for key in ["received", "under_review", "approved", "printed", "ready", "collected"] if stage_map[key].order <= target_order and key not in ("collected",)]
            if target_key == "collected":
                active_path = [stage_map[k] for k in ["received", "under_review", "approved", "printed", "ready", "collected"]]
            if target_key in ("on_hold", "rejected"):
                active_path = [stage_map[k] for k in ["received", "under_review", "approved"]]
                if target_key == "rejected":
                    active_path.append(stage_map["rejected"])
            # In some early-stage applications, only the first stage has been reached.
            current_stage = stage_map[target_key]
            status = "collected" if target_key == "collected" else "on_hold" if target_key == "on_hold" else "rejected" if target_key == "rejected" else "active"
            application = Application.objects.create(
                tracking_code=code, applicant=applicant, office=office,
                application_type=random.choice(["new", "new", "renewal", "replacement"]),
                current_stage=current_stage, status=status, received_at=received_at,
                previous_stage=stage_map["approved"] if target_key == "on_hold" else None,
            )
            dates = []
            path_end = now - timedelta(days=1) if target_key == "on_hold" else now
            if len(active_path) == 1:
                dates = [received_at]
            else:
                for j in range(len(active_path)):
                    dates.append(received_at + (path_end - received_at) * (j / (len(active_path) - 1)))
            previous = None
            for stage, at in zip(active_path, dates):
                actor = users["officer"] if random.random() < .8 else users["supervisor"]
                reason = "Application registered" if previous is None else "Status updated in demo data"
                change = StageChange.objects.create(application=application, from_stage=previous, to_stage=stage, by_user=actor, reason=reason, at=at)
                if stage.notify:
                    message = render_message(application, stage.key)
                    # Console demo rows are marked sent because provider delivery is simulated.
                    status_code = "failed" if random.random() < 0.035 else ("delivered" if random.random() < 0.45 else "sent")
                    Notification.objects.create(
                        application=application, channel="sms", to=applicant.phone, template_key=stage.key, body=message,
                        status=status_code, provider_ref=f"demo-{i}-{stage.key}", error="Demo delivery failure" if status_code == "failed" else "",
                        created_at=at, sent_at=at if status_code in ("sent", "delivered") else None,
                    )
                previous = stage
            if target_key == "on_hold":
                hold_at = now - timedelta(hours=1)
                StageChange.objects.create(application=application, from_stage=stage_map["approved"], to_stage=stage_map["on_hold"], by_user=users["supervisor"], reason="Waiting for supporting document", at=hold_at)
                if stage_map["on_hold"].notify:
                    Notification.objects.create(application=application, channel="sms", to=applicant.phone, template_key="on_hold", body=render_message(application, "on_hold"), status="sent", provider_ref=f"demo-{i}-hold", created_at=hold_at, sent_at=hold_at)
            created_count += 1
        self.stdout.write(self.style.SUCCESS(f"PASTNS demo ready: {created_count} applications added, {Application.objects.filter(office=office).count()} total."))
        self.stdout.write("Demo users: officer/officer123 · supervisor/super123 · admin/admin123")
        self.stdout.write(f"API token (supervisor): {Token.objects.get(user=users['supervisor']).key}")
