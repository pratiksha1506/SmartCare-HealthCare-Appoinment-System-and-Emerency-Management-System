from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import zoneinfo
from core.models import PatientProfile, DoctorProfile


class Appointment(models.Model):
    STATUS_CHOICES = (
        ('SCHEDULED', 'Scheduled'),
        ('CONFIRMED', 'Confirmed'),
        ('CHECKED_IN', 'Checked In'),
        ('IN_CONSULTATION', 'In Consultation'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('DELAYED_BY_EMERGENCY', 'Delayed by Emergency'),
    )

    REASON_CHOICES = (
        ('general', 'General health concern'),
        ('skin_hair', 'Skin or hair concern'),
        ('heart', 'Heart-related concern'),
        ('bone_joint', 'Bone or joint concern'),
        ('eye', 'Eye concern'),
        ('ent', 'Ear, nose or throat concern'),
        ('digestive', 'Digestive concern'),
        ('child_health', 'Child health concern'),
        ('neurological', 'Neurological concern'),
        ('other', 'Other'),
    )

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='appointments')
    
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    expected_duration_minutes = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='SCHEDULED')
    
    consultation_reason = models.CharField(max_length=50, choices=REASON_CHOICES, default='general')
    symptoms_description = models.TextField(blank=True, help_text="Short description of presenting symptoms")
    health_concern = models.TextField(blank=True, help_text="Optional description of symptoms or concern")
    
    # Patient travel & routing fields
    patient_origin_address = models.CharField(max_length=255, blank=True)
    patient_origin_lat = models.FloatField(null=True, blank=True)
    patient_origin_lng = models.FloatField(null=True, blank=True)
    
    hospital_destination_name = models.CharField(max_length=150, blank=True)
    hospital_destination_address = models.CharField(max_length=255, blank=True)
    
    estimated_travel_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    safety_buffer_minutes = models.PositiveIntegerField(default=15)
    recommended_departure_time = models.DateTimeField(null=True, blank=True)
    estimated_arrival_time = models.DateTimeField(null=True, blank=True)
    
    routing_provider_used = models.CharField(max_length=50, blank=True)
    routing_note = models.CharField(max_length=255, blank=True)
    last_travel_update = models.DateTimeField(null=True, blank=True)
    
    # Schedule disruption details
    delayed_by_minutes = models.PositiveIntegerField(default=0)
    schedule_disruption_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['appointment_date', 'appointment_time']
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'appointment_date', 'appointment_time'],
                condition=~models.Q(status='CANCELLED'),
                name='unique_active_doctor_appointment_slot'
            )
        ]

    def __str__(self):
        return f"{self.patient.user.get_full_name()} with {self.doctor} on {self.appointment_date} at {self.appointment_time}"

    @property
    def appointment_datetime(self):
        """Returns localized start datetime, adjusted for any emergency delays."""
        base_dt = datetime.combine(self.appointment_date, self.appointment_time)
        tz = zoneinfo.ZoneInfo(getattr(settings, 'TIME_ZONE', 'UTC'))
        localized_dt = base_dt.replace(tzinfo=tz)
        if self.delayed_by_minutes > 0:
            localized_dt += timedelta(minutes=self.delayed_by_minutes)
        return localized_dt

    @property
    def original_datetime(self):
        """Returns localized start datetime without emergency delays."""
        base_dt = datetime.combine(self.appointment_date, self.appointment_time)
        tz = zoneinfo.ZoneInfo(getattr(settings, 'TIME_ZONE', 'UTC'))
        return base_dt.replace(tzinfo=tz)

    def calculate_departure_schedule(self, travel_duration_minutes=None, buffer_minutes=None):
        """
        Calculates recommended departure time and estimated arrival time:
        Recommended Departure Time = Appointment Start Time - Estimated Travel Duration - Safety Buffer.
        Estimated Arrival Time = Recommended Departure Time + Estimated Travel Duration.
        """
        if travel_duration_minutes is not None:
            self.estimated_travel_duration_minutes = int(travel_duration_minutes)
        if buffer_minutes is not None:
            self.safety_buffer_minutes = int(buffer_minutes)
            
        if self.estimated_travel_duration_minutes is None:
            return None

        start_dt = self.appointment_datetime
        total_offset_minutes = self.estimated_travel_duration_minutes + self.safety_buffer_minutes
        
        departure_dt = start_dt - timedelta(minutes=total_offset_minutes)
        arrival_dt = departure_dt + timedelta(minutes=self.estimated_travel_duration_minutes)
        
        self.recommended_departure_time = departure_dt
        self.estimated_arrival_time = arrival_dt
        self.last_travel_update = timezone.now()
        return departure_dt

    @property
    def is_time_to_leave(self):
        """Returns True if current time is within 20 minutes of departure or already past it."""
        if not self.recommended_departure_time or self.status in ['COMPLETED', 'CANCELLED']:
            return False
        now = timezone.now()
        diff = (self.recommended_departure_time - now).total_seconds() / 60
        return diff <= 20 and now <= self.appointment_datetime


class ScheduleDisruption(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='disruptions')
    disruption_date = models.DateField()
    start_time = models.TimeField(help_text="Time from which the emergency delay starts affecting appointments")
    delay_minutes = models.PositiveIntegerField(help_text="Estimated delay in minutes")
    reason = models.TextField(help_text="Clinical justification / emergency context")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Emergency Disruption: {self.doctor} on {self.disruption_date} (+{self.delay_minutes}m)"

    def apply_to_appointments(self):
        affected = Appointment.objects.filter(
            doctor=self.doctor,
            appointment_date=self.disruption_date,
            appointment_time__gte=self.start_time,
            status__in=['SCHEDULED', 'CONFIRMED']
        )
        count = 0
        for apt in affected:
            apt.status = 'DELAYED_BY_EMERGENCY'
            apt.delayed_by_minutes = self.delay_minutes
            apt.schedule_disruption_notes = f"Emergency case delay recorded: {self.reason}"
            if apt.estimated_travel_duration_minutes:
                apt.calculate_departure_schedule()
            apt.save()
            count += 1
        return count


class ConsultationRecord(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='consultation_record')
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='consultation_records')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='consultation_records')
    
    clinical_notes = models.TextField(blank=True, help_text="Clinical observations and examination notes")
    diagnosis = models.TextField(blank=True, help_text="Clinical assessment / diagnosis")
    treatment_plan = models.TextField(blank=True, help_text="Recommended management and therapy")
    prescribed_medications = models.TextField(blank=True, help_text="Prescribed drugs, dosage and instructions")
    follow_up_instructions = models.TextField(blank=True, help_text="Follow-up advice and warnings")
    follow_up_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Consultation for {self.patient} by {self.doctor} ({self.created_at.strftime('%Y-%m-%d')})"
