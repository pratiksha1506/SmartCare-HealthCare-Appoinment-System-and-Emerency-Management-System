from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.db.models import Q
from django.db import transaction
from django.conf import settings

from core.views import patient_required, doctor_required, clinical_staff_required
from core.models import DoctorProfile, PatientProfile
from .models import Appointment, ScheduleDisruption, ConsultationRecord
from .forms import AppointmentBookingForm, ScheduleDisruptionForm, ConsultationForm
from emergency.models import EmergencyPatient
from emergency.queue import EmergencyPriorityQueue
from routing.services import RoutingService


# Symptom/Concern to Specialization Mapping with non-diagnostic clinical disclaimer
HEALTH_CONCERNS_MAP = [
    {
        'id': 'general',
        'title': 'General Health Concern / Routine Wellness',
        'specialization': 'General Medicine',
        'description': 'Routine exam, cold/flu, fatigue, general health assessment.'
    },
    {
        'id': 'skin_hair',
        'title': 'Skin or Hair Concern / Rashes',
        'specialization': 'Dermatology',
        'description': 'Skin lesions, acne, hair loss, dermatitis, eczema.'
    },
    {
        'id': 'heart',
        'title': 'Heart-Related Concern / Palpitations',
        'specialization': 'Cardiology',
        'description': 'Non-acute palpitations, blood pressure check, cardiovascular screening.'
    },
    {
        'id': 'bone_joint',
        'title': 'Bone or Joint Concern / Discomfort',
        'specialization': 'Orthopedics',
        'description': 'Joint pain, chronic back pain, sprains, post-injury mobility queries.'
    },
    {
        'id': 'eye',
        'title': 'Eye Concern / Vision Queries',
        'specialization': 'Ophthalmology',
        'description': 'Blurry vision, refractive check, eye strain, dry eyes.'
    },
    {
        'id': 'ent',
        'title': 'Ear, Nose or Throat Concern',
        'specialization': 'ENT / Otorhinolaryngology',
        'description': 'Earache, chronic sinus congestion, recurring sore throat.'
    },
    {
        'id': 'digestive',
        'title': 'Digestive Concern / Acid Reflux',
        'specialization': 'Gastroenterology',
        'description': 'Heartburn, digestive discomfort, bloating, non-acute abdominal queries.'
    },
    {
        'id': 'child_health',
        'title': 'Child Health Concern / Pediatric Check',
        'specialization': 'Pediatrics',
        'description': 'Infant growth milestones, pediatric general consultations.'
    },
    {
        'id': 'neurological',
        'title': 'Neurological Concern / Headaches',
        'specialization': 'Neurology',
        'description': 'Recurrent migraines, vertigo, tingling sensations.'
    },
    {
        'id': 'other',
        'title': 'Other Clinical Concern',
        'specialization': 'General Medicine',
        'description': 'Other non-emergency healthcare queries.'
    },
]


def find_doctors_view(request):
    concern_filter = request.GET.get('concern', '').strip()
    specialization_filter = request.GET.get('specialization', '').strip()
    query = request.GET.get('q', '').strip()
    max_fee = request.GET.get('max_fee', '').strip()

    # Single-hospital system: all doctors belong to the hospital; show active doctors
    doctors = DoctorProfile.objects.filter(is_active=True).select_related('user')

    matched_concern = None
    if concern_filter:
        for c in HEALTH_CONCERNS_MAP:
            if c['id'] == concern_filter:
                specialization_filter = c['specialization']
                matched_concern = c
                break

    if specialization_filter:
        doctors = doctors.filter(specialization__icontains=specialization_filter)

    if query:
        doctors = doctors.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(specialization__icontains=query) |
            Q(qualification__icontains=query)
        )

    if max_fee:
        try:
            doctors = doctors.filter(consultation_fee__lte=float(max_fee))
        except ValueError:
            pass

    return render(request, 'find_doctors.html', {
        'doctors': doctors,
        'specializations': [s[0] for s in DoctorProfile.SPECIALIZATION_CHOICES],
        'concerns_map': HEALTH_CONCERNS_MAP,
        'selected_specialization': specialization_filter,
        'selected_concern': concern_filter,
        'matched_concern': matched_concern,
        'query': query,
        'max_fee': max_fee,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
        'hospital_address': getattr(settings, 'DEFAULT_HOSPITAL_ADDRESS', '100 Healthcare Blvd, Metro City'),
    })


def get_available_slots_api(request):
    doctor_id = request.GET.get('doctor_id')
    date_str = request.GET.get('date')

    if not doctor_id or not date_str:
        return JsonResponse({'error': 'Doctor ID and Date are required.'}, status=400)

    try:
        doctor = DoctorProfile.objects.get(id=doctor_id)
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (DoctorProfile.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Invalid doctor or date format.'}, status=400)

    slots = AppointmentBookingForm.doctor_available_slots(doctor, selected_date)
    formatted_slots = [
        {
            'value': s.strftime('%H:%M:%S'),
            'label': s.strftime('%I:%M %p')
        }
        for s in slots
    ]

    return JsonResponse({
        'doctor_id': doctor.id,
        'doctor_name': f"Dr. {doctor.user.get_full_name()}",
        'date': date_str,
        'slots': formatted_slots,
        'count': len(formatted_slots)
    })


@login_required
@patient_required
def book_appointment_view(request, doctor_id):
    doctor = get_object_or_404(DoctorProfile, id=doctor_id, is_active=True)
    patient_profile = request.user.patient_profile

    hospital_name = getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital')
    hospital_address = getattr(settings, 'DEFAULT_HOSPITAL_ADDRESS', '100 Healthcare Blvd, Metro City')
    hospital_lat = getattr(settings, 'DEFAULT_HOSPITAL_LAT', 12.971598)
    hospital_lng = getattr(settings, 'DEFAULT_HOSPITAL_LNG', 77.594562)

    if request.method == 'POST':
        form = AppointmentBookingForm(doctor=doctor, patient=patient_profile, data=request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = patient_profile
            appointment.doctor = doctor
            appointment.hospital_destination_name = hospital_name
            appointment.hospital_destination_address = hospital_address
            appointment.status = 'SCHEDULED'
            appointment.health_concern = f"[{appointment.get_consultation_reason_display()}] {appointment.symptoms_description}"

            # Routing and Smart Departure-Time Calculation
            origin_lat = form.cleaned_data.get('patient_origin_lat')
            origin_lng = form.cleaned_data.get('patient_origin_lng')
            origin_address = form.cleaned_data.get('patient_origin_address', '')
            safety_buffer = int(form.cleaned_data.get('safety_buffer_minutes', 15))

            routing_result = RoutingService.get_route_and_departure(
                appointment_date=appointment.appointment_date,
                appointment_time=appointment.appointment_time,
                dest_lat=hospital_lat,
                dest_lng=hospital_lng,
                dest_name=hospital_name,
                dest_address=hospital_address,
                origin_lat=origin_lat,
                origin_lng=origin_lng,
                origin_address=origin_address,
                safety_buffer_minutes=safety_buffer,
            )

            appointment.estimated_travel_duration_minutes = routing_result.duration_minutes
            appointment.safety_buffer_minutes = routing_result.safety_buffer_minutes
            appointment.recommended_departure_time = routing_result.recommended_departure_time
            appointment.estimated_arrival_time = routing_result.estimated_arrival_time
            appointment.routing_provider_used = routing_result.provider
            appointment.routing_note = routing_result.traffic_status_message
            appointment.last_travel_update = timezone.now()

            appointment.save()

            messages.success(
                request,
                f"Appointment confirmed with Dr. {doctor.user.get_full_name()} for {appointment.appointment_date} at {appointment.appointment_time.strftime('%I:%M %p')}. "
                f"Recommended departure: {appointment.recommended_departure_time.strftime('%I:%M %p')}."
            )
            return redirect('appointment_detail', appointment_id=appointment.id)
    else:
        initial_data = {
            'appointment_date': timezone.now().date(),
            'safety_buffer_minutes': 15,
            'patient_origin_address': patient_profile.default_address or '',
        }
        form = AppointmentBookingForm(doctor=doctor, patient=patient_profile, initial=initial_data)

    return render(request, 'book_appointment.html', {
        'form': form,
        'doctor': doctor,
        'patient_profile': patient_profile,
        'hospital_name': hospital_name,
        'hospital_address': hospital_address,
        'hospital_lat': hospital_lat,
        'hospital_lng': hospital_lng,
        'emergency_hotline': getattr(settings, 'HOSPITAL_EMERGENCY_PHONE', '+1 (555) 911-CARE'),
        'emergency_department': getattr(settings, 'HOSPITAL_EMERGENCY_DEPARTMENT', 'SmartCare Emergency & Trauma Pavilion, Gate 2'),
    })


@login_required
@patient_required
def patient_dashboard_view(request):
    patient_profile = request.user.patient_profile
    now = timezone.now()

    # STRICT FILTERING: Only the authenticated patient's appointments are retrieved
    upcoming_appointments = Appointment.objects.filter(
        patient=patient_profile,
        appointment_date__gte=now.date(),
        status__in=['SCHEDULED', 'CONFIRMED', 'DELAYED_BY_EMERGENCY']
    ).select_related('doctor', 'doctor__user').order_by('appointment_date', 'appointment_time')

    past_appointments = Appointment.objects.filter(
        patient=patient_profile
    ).filter(
        Q(appointment_date__lt=now.date()) | Q(status__in=['COMPLETED', 'CANCELLED'])
    ).select_related('doctor', 'doctor__user').order_by('-appointment_date', '-appointment_time')[:10]

    # Active "Time to Leave" alerts
    active_alerts = [apt for apt in upcoming_appointments if apt.is_time_to_leave]

    # Emergency Queue Status for this patient (Feature 7)
    emergency_case = EmergencyPatient.objects.filter(
        patient_profile=patient_profile
    ).order_by('-arrival_time').first()

    emergency_status_data = None
    if emergency_case:
        queue = EmergencyPriorityQueue.get_active_queue_from_db()
        emergency_status_data = queue.get_patient_queue_position(emergency_case.id)

    return render(request, 'patient_dashboard.html', {
        'patient_profile': patient_profile,
        'upcoming_appointments': upcoming_appointments,
        'past_appointments': past_appointments,
        'active_alerts': active_alerts,
        'emergency_status_data': emergency_status_data,
        'current_time': now,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


@login_required
@doctor_required
def doctor_dashboard_view(request):
    """
    CRITICAL: Strict Doctor-Specific Appointment Filtering.
    When a doctor logs in, display ONLY appointments whose assigned doctor
    is that authenticated doctor.
    """
    doctor_profile = request.user.doctor_profile
    today = timezone.localdate()

    # Backend enforces doctor_profile ownership filter
    today_appointments = Appointment.objects.filter(
        doctor=doctor_profile,
        appointment_date=today
    ).select_related('patient', 'patient__user').order_by('appointment_time')

    upcoming_appointments = Appointment.objects.filter(
        doctor=doctor_profile,
        appointment_date__gt=today,
        status__in=['SCHEDULED', 'CONFIRMED', 'DELAYED_BY_EMERGENCY']
    ).select_related('patient', 'patient__user').order_by('appointment_date', 'appointment_time')[:20]

    completed_appointments = Appointment.objects.filter(
        doctor=doctor_profile,
        status='COMPLETED'
    ).select_related('patient', 'patient__user').order_by('-appointment_date', '-appointment_time')[:15]

    cancelled_appointments = Appointment.objects.filter(
        doctor=doctor_profile,
        status='CANCELLED'
    ).select_related('patient', 'patient__user').order_by('-appointment_date', '-appointment_time')[:15]

    # Emergency summary for hospital awareness
    active_emergencies = EmergencyPatient.objects.filter(status__in=['WAITING', 'UNDER_ASSESSMENT'])
    critical_count = active_emergencies.filter(priority_level=1).count()
    urgent_count = active_emergencies.filter(priority_level=2).count()
    less_urgent_count = active_emergencies.filter(priority_level=3).count()

    disruption_form = ScheduleDisruptionForm()

    return render(request, 'doctor_dashboard.html', {
        'doctor_profile': doctor_profile,
        'today_appointments': today_appointments,
        'upcoming_appointments': upcoming_appointments,
        'completed_appointments': completed_appointments,
        'cancelled_appointments': cancelled_appointments,
        'today': today,
        'emergency_summary': {
            'total': active_emergencies.count(),
            'critical': critical_count,
            'urgent': urgent_count,
            'less_urgent': less_urgent_count,
        },
        'disruption_form': disruption_form,
    })


@login_required
def appointment_detail_view(request, appointment_id):
    """
    Strict ownership verification on appointment detail pages:
    - Doctor can ONLY view appointments assigned to them.
    - Patient can ONLY view appointments booked by them.
    - Hospital administrators have appropriate oversight access.
    """
    appointment = get_object_or_404(
        Appointment.objects.select_related('doctor', 'doctor__user', 'patient', 'patient__user'),
        id=appointment_id
    )

    user = request.user
    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'admin'

    if user.is_doctor:
        if appointment.doctor.user != user and not is_admin:
            return HttpResponseForbidden("Access Denied: You cannot view another doctor's appointments.")
    elif user.is_patient:
        if appointment.patient.user != user and not is_admin:
            return HttpResponseForbidden("Access Denied: You cannot view another patient's appointment.")
    elif not is_admin:
        return HttpResponseForbidden("Access Denied: Insufficient permissions to view this appointment.")

    return render(request, 'appointment_detail.html', {
        'appointment': appointment,
        'doctor': appointment.doctor,
        'patient': appointment.patient,
        'is_time_to_leave': appointment.is_time_to_leave,
    })


@login_required
def cancel_appointment_view(request, appointment_id):
    """
    Strict ownership verification on appointment cancellation:
    - Patient can only cancel their own appointment.
    - Doctor can only cancel appointments booked specifically with them.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)
    user = request.user
    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'admin'

    if user.is_patient and appointment.patient.user != user and not is_admin:
        return HttpResponseForbidden("Access Denied: You cannot cancel another patient's appointment.")
    if user.is_doctor and appointment.doctor.user != user and not is_admin:
        return HttpResponseForbidden("Access Denied: You cannot cancel another doctor's appointment.")
    if not (user.is_patient or user.is_doctor or is_admin):
        return HttpResponseForbidden("Access Denied: Insufficient permissions.")

    if request.method == 'POST':
        appointment.status = 'CANCELLED'
        appointment.save()
        messages.success(request, f"Appointment on {appointment.appointment_date} at {appointment.appointment_time.strftime('%I:%M %p')} has been cancelled.")
        if user.is_patient:
            return redirect('patient_dashboard')
        return redirect('doctor_dashboard')

    return render(request, 'cancel_confirm.html', {'appointment': appointment})


@login_required
@doctor_required
def update_appointment_status_view(request, appointment_id):
    """
    Doctor updates status of their own appointment.
    """
    user = request.user
    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'admin'

    appointment = get_object_or_404(Appointment, id=appointment_id)
    if appointment.doctor.user != user and not is_admin:
        return HttpResponseForbidden("Access Denied: You cannot modify another doctor's appointment.")

    new_status = request.POST.get('status')
    valid_statuses = dict(Appointment.STATUS_CHOICES).keys()

    if new_status in valid_statuses:
        appointment.status = new_status
        appointment.save()
        messages.success(request, f"Appointment status updated to '{appointment.get_status_display()}'.")
    else:
        messages.error(request, "Invalid appointment status specified.")

    return redirect('doctor_dashboard')


@login_required
def record_disruption_view(request):
    """
    Doctor records an emergency disruption for their own schedule,
    or Hospital Administrator records for an assigned doctor.
    """
    user = request.user
    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'admin'

    if request.method == 'POST':
        form = ScheduleDisruptionForm(request.POST)
        if form.is_valid():
            disruption = form.save(commit=False)
            
            if user.is_doctor:
                disruption.doctor = user.doctor_profile
            elif is_admin:
                doctor_id = request.POST.get('doctor_id')
                if not doctor_id:
                    messages.error(request, "Please select the affected doctor.")
                    return redirect('doctor_dashboard')
                disruption.doctor = get_object_or_404(DoctorProfile, id=doctor_id)
            else:
                return HttpResponseForbidden("Access Denied.")

            disruption.disruption_date = timezone.localdate()
            disruption.recorded_by = user
            disruption.save()

            count = disruption.apply_to_appointments()
            messages.warning(
                request,
                f"Emergency schedule disruption of +{disruption.delay_minutes} minutes recorded for Dr. {disruption.doctor.user.get_full_name()}. "
                f"{count} upcoming appointments adjusted."
            )
            return redirect('doctor_dashboard')
        else:
            messages.error(request, "Please check the disruption details and try again.")

    return redirect('doctor_dashboard')


@login_required
def doctor_consultation_view(request, appointment_id):
    """
    Doctor's patient consultation and clinical documentation portal.
    CRITICAL SECURITY RULE:
    A doctor may ONLY open a patient's consultation and record through an appointment
    specifically assigned to that doctor. Any attempt by another doctor or unauthorized
    user to access this record must be rejected with 403 Forbidden.
    """
    appointment = get_object_or_404(
        Appointment.objects.select_related('doctor', 'doctor__user', 'patient', 'patient__user'),
        id=appointment_id
    )

    user = request.user
    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'admin'

    # STRICT ACCESS CHECK: Only the assigned doctor or an authorized hospital administrator can access
    if user.is_doctor:
        if appointment.doctor.user != user and not is_admin:
            return HttpResponseForbidden("Access Denied: You cannot access clinical records or consultations for another doctor's patient.")
    elif not is_admin:
        return HttpResponseForbidden("Access Denied: Clinician or hospital administrator credentials required.")

    patient = appointment.patient
    doctor = appointment.doctor

    # Retrieve or initialize ConsultationRecord for this appointment
    consultation_record = getattr(appointment, 'consultation_record', None)

    # Previous consultations for this patient across visits (historical records)
    past_consultations = ConsultationRecord.objects.filter(
        patient=patient
    ).exclude(appointment=appointment).select_related('doctor', 'doctor__user', 'appointment').order_by('-created_at')

    if request.method == 'POST':
        action = request.POST.get('action')

        # Quick action: Start Consultation
        if action == 'start_consultation':
            if appointment.status in ['SCHEDULED', 'CONFIRMED', 'CHECKED_IN']:
                appointment.status = 'IN_CONSULTATION'
                appointment.save()
                messages.info(request, f"Consultation started with {patient.user.get_full_name()}. Status updated to 'In Consultation'.")
            return redirect('doctor_consultation', appointment_id=appointment.id)

        form = ConsultationForm(request.POST, instance=consultation_record, patient=patient)
        if form.is_valid():
            with transaction.atomic():
                record = form.save(commit=False)
                record.appointment = appointment
                record.patient = patient
                record.doctor = doctor
                record.save()

                # Update patient medical history if provided
                updated_history = form.cleaned_data.get('patient_medical_history')
                if updated_history is not None and updated_history != patient.medical_history:
                    patient.medical_history = updated_history
                    patient.save()

                # Update appointment status
                status_choice = form.cleaned_data.get('appointment_status')
                if status_choice:
                    appointment.status = status_choice
                    appointment.save()

            messages.success(request, f"Clinical consultation notes for {patient.user.get_full_name()} saved successfully.")
            if appointment.status == 'COMPLETED':
                messages.success(request, f"Appointment #{appointment.id} marked as Completed.")
                return redirect('doctor_dashboard')
            return redirect('doctor_consultation', appointment_id=appointment.id)
    else:
        # Prepopulate form
        initial_data = {}
        if not consultation_record:
            if appointment.status in ['SCHEDULED', 'CONFIRMED', 'CHECKED_IN']:
                initial_data['appointment_status'] = 'IN_CONSULTATION'
        else:
            initial_data['appointment_status'] = appointment.status

        form = ConsultationForm(instance=consultation_record, patient=patient, initial=initial_data)

    return render(request, 'doctor_consultation.html', {
        'appointment': appointment,
        'patient': patient,
        'doctor': doctor,
        'consultation_record': consultation_record,
        'past_consultations': past_consultations,
        'form': form,
    })


@login_required
def check_in_appointment_view(request, appointment_id):
    """
    Marks an appointment as CHECKED_IN.
    Can be performed by the assigned doctor, clinical staff, or administrator.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)
    user = request.user
    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'admin'
    is_assigned_doctor = user.is_doctor and appointment.doctor.user == user
    is_staff = getattr(user, 'is_clinical_staff', False)

    if not (is_assigned_doctor or is_admin or is_staff):
        return HttpResponseForbidden("Access Denied: Only the assigned clinician or clinical staff can check in this appointment.")

    if request.method == 'POST':
        appointment.status = 'CHECKED_IN'
        appointment.save()
        messages.success(request, f"Patient {appointment.patient.user.get_full_name()} checked in successfully.")

    if user.is_doctor:
        return redirect('doctor_dashboard')
    elif is_admin:
        return redirect('admin_appointment_list')
    return redirect('dashboard_redirect')


@login_required
@doctor_required
def doctor_patient_record_view(request, patient_id):
    """
    Direct access to a patient's medical record by a doctor.
    SECURITY RULE:
    A doctor must NOT be able to access an unrelated patient's private records
    simply by guessing a patient ID. Access is strictly denied (403 Forbidden)
    unless an authorized care relationship (at least one appointment with this doctor)
    exists.
    """
    doctor = request.user.doctor_profile
    patient = get_object_or_404(PatientProfile.objects.select_related('user'), id=patient_id)

    has_relationship = Appointment.objects.filter(doctor=doctor, patient=patient).exists()
    if not has_relationship and not (request.user.is_admin or request.user.is_superuser):
        return HttpResponseForbidden("Access Denied: You have no active or prior appointments with this patient.")

    latest_appointment = Appointment.objects.filter(
        doctor=doctor, patient=patient
    ).order_by('-appointment_date', '-appointment_time').first()

    if latest_appointment:
        return redirect('doctor_consultation', appointment_id=latest_appointment.id)

    return HttpResponseForbidden("Access Denied: No appointment found for this patient.")
