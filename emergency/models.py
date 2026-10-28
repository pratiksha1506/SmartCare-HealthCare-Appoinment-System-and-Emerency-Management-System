from django.db import models
from django.conf import settings
from django.utils import timezone


class EmergencyPatient(models.Model):
    PRIORITY_CHOICES = (
        (1, 'Priority 1 - Critical (Red: Immediate resuscitation / life-threatening)'),
        (2, 'Priority 2 - Urgent (Orange: Potential rapid deterioration / severe distress)'),
        (3, 'Priority 3 - Less Urgent (Green: Stable vitals / standard emergency care)'),
    )

    STATUS_CHOICES = (
        ('WAITING', 'Waiting for Clinical Triage / Care'),
        ('UNDER_ASSESSMENT', 'Under Active Clinical Assessment'),
        ('ADMITTED', 'Admitted to Inpatient / ICU'),
        ('DISCHARGED', 'Discharged Post-Treatment'),
        ('TRANSFERRED', 'Transferred to Specialized Trauma Center'),
    )

    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    )

    patient_code = models.CharField(max_length=30, unique=True, editable=False)
    
    # Optional link to registered patient profile if patient has an account
    patient_profile = models.ForeignKey(
        'core.PatientProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emergency_cases'
    )

    full_name = models.CharField(max_length=150)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='prefer_not_to_say')
    contact_number = models.CharField(max_length=30, blank=True)

    priority_level = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='WAITING')

    chief_complaint = models.TextField(help_text="Primary symptoms or incident reported upon presentation")
    triage_notes = models.TextField(blank=True, help_text="Clinical observations recorded by triage staff")

    arrival_time = models.DateTimeField(default=timezone.now)
    assessed_at = models.DateTimeField(null=True, blank=True)
    discharged_at = models.DateTimeField(null=True, blank=True)

    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_emergencies'
    )
    attending_clinician = models.ForeignKey(
        'core.DoctorProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emergency_patients'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority_level', 'arrival_time']

    def save(self, *args, **kwargs):
        if not self.patient_code:
            today_str = timezone.now().strftime('%Y%m%d')
            count = EmergencyPatient.objects.filter(created_at__date=timezone.now().date()).count() + 1
            self.patient_code = f"EP-{today_str}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.patient_code}] {self.full_name} ({self.priority_name})"

    @property
    def priority_name(self):
        if self.priority_level == 1:
            return "Critical (Red)"
        elif self.priority_level == 2:
            return "Urgent (Orange)"
        return "Less Urgent (Green)"

    @property
    def waiting_duration_seconds(self):
        end_time = self.assessed_at or timezone.now()
        diff = (end_time - self.arrival_time).total_seconds()
        return max(0, int(diff))

    @property
    def waiting_duration_display(self):
        total_seconds = self.waiting_duration_seconds
        minutes = total_seconds // 60
        hours = minutes // 60
        rem_minutes = minutes % 60
        if hours > 0:
            return f"{hours}h {rem_minutes}m"
        return f"{rem_minutes}m"

    @property
    def is_eligible_for_queue(self):
        return self.status in ['WAITING', 'UNDER_ASSESSMENT']


class PriorityAssessmentLog(models.Model):
    emergency_patient = models.ForeignKey(EmergencyPatient, on_delete=models.CASCADE, related_name='assessment_history')
    previous_priority = models.IntegerField()
    new_priority = models.IntegerField()
    clinical_rationale = models.TextField(help_text="Clinical justification for priority adjustment")
    assessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.emergency_patient.patient_code}: P{self.previous_priority} -> P{self.new_priority} at {self.timestamp.strftime('%H:%M')}"
