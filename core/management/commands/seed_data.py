from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import User


class Command(BaseCommand):
    help = 'Ensures administrator account and single-hospital system configuration are initialized'

    def handle(self, *args, **kwargs):
        self.stdout.write("Initializing SmartCare single-hospital environment...")

        # Create or ensure default Hospital Administrator / Staff User
        admin_user, created = User.objects.get_or_create(
            username='admin@smartcare.org',
            defaults={
                'email': 'admin@smartcare.org',
                'first_name': 'Chief',
                'last_name': 'Administrator',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'contact_number': '+1 (555) 0100'
            }
        )
        if created:
            admin_user.set_password('AdminPass123!')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created hospital administrator account: admin@smartcare.org / AdminPass123!"))
        else:
            admin_user.role = 'admin'
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Hospital administrator account verified: admin@smartcare.org"))

        self.stdout.write(f"Hospital Name: {getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital')}")
        self.stdout.write(f"Hospital Address: {getattr(settings, 'DEFAULT_HOSPITAL_ADDRESS', '100 Healthcare Blvd, Metro City')}")
        self.stdout.write(self.style.SUCCESS("SmartCare initialized without sample doctors or mock data. Doctors can now be added by the administrator."))
