from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class User(AbstractUser):
    ROLE_CHOICES = (
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
        ('staff', 'Clinical Staff'),
        ('admin', 'Administrator'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')
    contact_number = models.CharField(max_length=20, blank=True)

    @property
    def is_patient(self):
        return self.role == 'patient'

    @property
    def is_doctor(self):
        return self.role == 'doctor'

    @property
    def is_clinical_staff(self):
        # Only dedicated clinical staff or administrators have triage and clinical queue management rights
        return self.role in ['staff', 'admin'] or self.is_staff or self.is_superuser

    @property
    def is_admin(self):
        return self.role == 'admin' or self.is_staff or self.is_superuser


class PatientProfile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='prefer_not_to_say')
    medical_history = models.TextField(blank=True, help_text="Chronic conditions, allergies, past surgeries or relevant medical background")
    default_address = models.CharField(max_length=255, blank=True)
    default_lat = models.FloatField(null=True, blank=True)
    default_lng = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Patient: {self.user.get_full_name() or self.user.username}"


class DoctorProfile(models.Model):
    SPECIALIZATION_CHOICES = (
        ('General Medicine', 'General Medicine'),
        ('Cardiology', 'Cardiology'),
        ('Neurology', 'Neurology'),
        ('Dermatology', 'Dermatology'),
        ('Orthopedics', 'Orthopedics'),
        ('Pediatrics', 'Pediatrics'),
        ('Ophthalmology', 'Ophthalmology'),
        ('Gastroenterology', 'Gastroenterology'),
        ('Pulmonology', 'Pulmonology'),
        ('Emergency Medicine', 'Emergency Medicine'),
        ('ENT / Otorhinolaryngology', 'ENT / Otorhinolaryngology'),
        ('Psychiatry', 'Psychiatry'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    specialization = models.CharField(max_length=100, choices=SPECIALIZATION_CHOICES, default='General Medicine')
    qualification = models.CharField(max_length=150)
    registration_number = models.CharField(max_length=50, unique=True)
    experience_years = models.PositiveIntegerField(default=1)
    
    # Single-hospital system: defaults to hospital configuration in settings
    hospital_name = models.CharField(max_length=150, default="SmartCare Central Hospital")
    hospital_address = models.CharField(max_length=255, default="100 Healthcare Blvd, Metro City")
    hospital_lat = models.FloatField(default=12.971598)
    hospital_lng = models.FloatField(default=77.594562)
    
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    available_days = models.CharField(max_length=150, default="Mon,Tue,Wed,Thu,Fri", help_text="Comma-separated working days e.g. Mon,Tue,Wed,Thu,Fri")
    availability_summary = models.CharField(max_length=200, default="Mon - Fri, 09:00 AM - 05:00 PM")
    slot_duration_minutes = models.PositiveIntegerField(default=30)
    work_start_time = models.TimeField(default="09:00:00")
    work_end_time = models.TimeField(default="17:00:00")
    is_active = models.BooleanField(default=True, help_text="Active doctors are displayed in search and available for appointments")
    is_accepting_emergencies = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username} ({self.specialization})"

    @property
    def current_hospital_name(self):
        return getattr(settings, 'DEFAULT_HOSPITAL_NAME', self.hospital_name)

    @property
    def current_hospital_address(self):
        return getattr(settings, 'DEFAULT_HOSPITAL_ADDRESS', self.hospital_address)
