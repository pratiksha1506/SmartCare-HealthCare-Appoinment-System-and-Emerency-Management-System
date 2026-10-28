from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, datetime, time, timedelta

from .models import Appointment, ScheduleDisruption, ConsultationRecord
from core.models import DoctorProfile


class AppointmentBookingForm(forms.ModelForm):
    triage_intent = forms.ChoiceField(
        choices=[
            ('routine', 'Routine consultation (I want to book an appointment with a specialist)'),
            ('emergency', 'Emergency medical assistance (I am experiencing an urgent medical emergency)'),
        ],
        initial='routine',
        widget=forms.RadioSelect(attrs={'class': 'triage-radio'}),
        label="Are you seeking a routine consultation or emergency medical assistance?"
    )

    consultation_reason = forms.ChoiceField(
        choices=Appointment.REASON_CHOICES,
        initial='general',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_consultation_reason'}),
        label="Primary Reason for Consultation"
    )

    symptoms_description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Provide a brief description of your symptoms or reason for visit...', 'class': 'form-control'}),
        required=False,
        label="Short Description of Symptoms"
    )

    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'id_appointment_date'}),
        label="Preferred Consultation Date"
    )

    appointment_time = forms.TimeField(
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_appointment_time'}),
        label="Available Time Slot"
    )

    patient_origin_address = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Enter starting address (e.g. 42 Main St, Metro City)', 'class': 'form-control', 'id': 'id_patient_origin_address'}),
        required=False,
        label="Starting Location for Journey Calculation"
    )
    patient_origin_lat = forms.FloatField(widget=forms.HiddenInput(attrs={'id': 'id_patient_origin_lat'}), required=False)
    patient_origin_lng = forms.FloatField(widget=forms.HiddenInput(attrs={'id': 'id_patient_origin_lng'}), required=False)
    
    safety_buffer_minutes = forms.ChoiceField(
        choices=[
            (10, '10 minutes (Quick buffer)'),
            (15, '15 minutes (Standard recommended)'),
            (20, '20 minutes (Relaxed buffer)'),
            (30, '30 minutes (High buffer)')
        ],
        initial=15,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_safety_buffer_minutes'}),
        label="Recommended Departure Safety Buffer"
    )

    class Meta:
        model = Appointment
        fields = [
            'consultation_reason',
            'symptoms_description',
            'appointment_date',
            'appointment_time',
            'patient_origin_address',
            'patient_origin_lat',
            'patient_origin_lng',
            'safety_buffer_minutes'
        ]

    def __init__(self, doctor=None, patient=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doctor = doctor
        self.patient = patient
        
        initial_date = self.data.get('appointment_date') or timezone.now().date()
        if isinstance(initial_date, str):
            try:
                initial_date = datetime.strptime(initial_date, '%Y-%m-%d').date()
            except ValueError:
                initial_date = timezone.now().date()
        
        if self.doctor:
            slots = self.doctor_available_slots(self.doctor, initial_date)
            self.fields['appointment_time'].widget.choices = [(s.strftime('%H:%M:%S'), s.strftime('%I:%M %p')) for s in slots]

    @staticmethod
    def doctor_available_slots(doctor: DoctorProfile, selected_date: date):
        """
        Generates available time slots within doctor working hours on active working days,
        excluding booked slots.
        """
        if not doctor.is_active:
            return []

        # Check working days
        day_abbr = selected_date.strftime('%a')  # 'Mon', 'Tue', etc.
        working_days = [d.strip() for d in doctor.available_days.split(',') if d.strip()]
        if working_days and day_abbr not in working_days:
            return []

        start_t = doctor.work_start_time
        end_t = doctor.work_end_time
        slot_dur = timedelta(minutes=doctor.slot_duration_minutes)

        current_dt = datetime.combine(selected_date, start_t)
        end_dt = datetime.combine(selected_date, end_t)

        booked_times = set(
            Appointment.objects.filter(
                doctor=doctor,
                appointment_date=selected_date
            ).exclude(status='CANCELLED').values_list('appointment_time', flat=True)
        )

        available = []
        now = timezone.localtime()
        while current_dt + slot_dur <= end_dt:
            slot_time = current_dt.time()
            if selected_date == now.date() and slot_time <= now.time():
                current_dt += slot_dur
                continue

            if slot_time not in booked_times:
                available.append(slot_time)
            current_dt += slot_dur

        return available

    def clean_triage_intent(self):
        intent = self.cleaned_data.get('triage_intent')
        if intent == 'emergency':
            raise ValidationError(
                "You have reported an acute medical emergency. "
                "Please do not book a routine appointment. Proceed directly to the hospital Emergency Department or call 911 / 112 immediately."
            )
        return intent

    def clean_appointment_date(self):
        appt_date = self.cleaned_data.get('appointment_date')
        if appt_date < timezone.now().date():
            raise ValidationError("You cannot book an appointment for a past date.")
        if appt_date > timezone.now().date() + timedelta(days=60):
            raise ValidationError("Appointments can only be scheduled up to 60 days in advance.")

        if self.doctor:
            day_abbr = appt_date.strftime('%a')
            working_days = [d.strip() for d in self.doctor.available_days.split(',') if d.strip()]
            if working_days and day_abbr not in working_days:
                raise ValidationError(f"Dr. {self.doctor.user.get_full_name()} does not consult on {appt_date.strftime('%A')}s. Available days: {self.doctor.available_days}.")

        return appt_date

    def clean(self):
        cleaned_data = super().clean()
        appt_date = cleaned_data.get('appointment_date')
        appt_time = cleaned_data.get('appointment_time')

        if appt_date and appt_time and self.doctor:
            # Check double booking for doctor
            conflict_doc = Appointment.objects.filter(
                doctor=self.doctor,
                appointment_date=appt_date,
                appointment_time=appt_time
            ).exclude(status='CANCELLED').exists()

            if conflict_doc:
                raise ValidationError(f"This time slot ({appt_time.strftime('%I:%M %p')}) is already booked with Dr. {self.doctor.user.get_full_name()}. Please select another slot.")

        if appt_date and appt_time and self.patient:
            # Check double booking for the same patient across any doctor
            conflict_patient = Appointment.objects.filter(
                patient=self.patient,
                appointment_date=appt_date,
                appointment_time=appt_time
            ).exclude(status='CANCELLED').exists()

            if conflict_patient:
                raise ValidationError(f"You already have a scheduled consultation at {appt_time.strftime('%I:%M %p')} on this date.")

        return cleaned_data


class ScheduleDisruptionForm(forms.ModelForm):
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        label="Disruption Start Time"
    )
    delay_minutes = forms.IntegerField(
        min_value=5,
        max_value=240,
        initial=30,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Estimated Delay Duration (Minutes)"
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. Dr. attending acute emergency resuscitation', 'class': 'form-control'}),
        label="Emergency Clinical Reason"
    )

    class Meta:
        model = ScheduleDisruption
        fields = ['start_time', 'delay_minutes', 'reason']


class ConsultationForm(forms.ModelForm):
    """
    Doctor's clinical consultation form to record examination notes, diagnosis,
    treatment plans, medications, and follow-up guidance.
    """
    patient_medical_history = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Known allergies, chronic conditions, surgical history...'}),
        required=False,
        label="Patient Medical History (Allergies, Chronic Diseases, Past Surgeries)"
    )
    clinical_notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Objective findings, vitals, examination notes...'}),
        required=False,
        label="Clinical Notes & Observations"
    )
    diagnosis = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Clinical assessment and primary diagnosis...'}),
        required=True,
        label="Clinical Diagnosis / Assessment"
    )
    treatment_plan = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Management plan, lifestyle advice, therapies...'}),
        required=False,
        label="Treatment Plan & Recommendations"
    )
    prescribed_medications = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Prescribed medications with dosage, frequency, and duration...'}),
        required=False,
        label="Prescribed Medications"
    )
    follow_up_instructions = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Warning signs to watch out for, precautions, follow-up advice...'}),
        required=False,
        label="Follow-up Instructions"
    )
    follow_up_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label="Recommended Follow-up Date"
    )
    appointment_status = forms.ChoiceField(
        choices=[
            ('IN_CONSULTATION', 'In Consultation'),
            ('COMPLETED', 'Completed (Finalize Consultation)'),
            ('SCHEDULED', 'Keep Scheduled'),
        ],
        initial='COMPLETED',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Consultation Status"
    )

    class Meta:
        model = ConsultationRecord
        fields = [
            'clinical_notes',
            'diagnosis',
            'treatment_plan',
            'prescribed_medications',
            'follow_up_instructions',
            'follow_up_date',
        ]

    def __init__(self, *args, **kwargs):
        patient = kwargs.pop('patient', None)
        super().__init__(*args, **kwargs)
        if patient:
            self.fields['patient_medical_history'].initial = patient.medical_history
