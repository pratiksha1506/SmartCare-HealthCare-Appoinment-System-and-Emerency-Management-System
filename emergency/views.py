from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.conf import settings

from core.views import clinical_staff_required, patient_required
from core.models import DoctorProfile, PatientProfile
from .models import EmergencyPatient, PriorityAssessmentLog
from .forms import EmergencyRegistrationForm, PriorityReassessmentForm, PatientEmergencyReportForm
from .queue import EmergencyPriorityQueue


@login_required
@clinical_staff_required
def emergency_queue_dashboard_view(request):
    """
    Primary Emergency Department Triage and Queue Management Dashboard.
    Rebuilds the genuine Python priority queue directly from the database.
    Only authorized clinical staff or administrators can access.
    """
    queue = EmergencyPriorityQueue.get_active_queue_from_db()

    registration_form = EmergencyRegistrationForm()
    doctors = DoctorProfile.objects.filter(is_active=True).select_related('user')

    if request.method == 'POST' and 'action' in request.POST:
        action = request.POST.get('action')

        if action == 'register_patient':
            reg_form = EmergencyRegistrationForm(request.POST)
            if reg_form.is_valid():
                patient = reg_form.save(commit=False)
                patient.registered_by = request.user
                patient.status = 'WAITING'
                patient.save()

                # Rebuild queue with new patient
                queue.rebuild_from_database()

                messages.success(
                    request,
                    f"Emergency Patient {patient.patient_code} ({patient.full_name}) registered with Priority {patient.priority_level} ({patient.priority_name})."
                )
                return redirect('emergency_queue_dashboard')
            else:
                registration_form = reg_form
                messages.error(request, "Please correct the errors in the emergency registration form.")

    active_queue_items = queue.get_queue_display_data()

    critical_count = sum(1 for item in active_queue_items if item['priority_level'] == 1)
    urgent_count = sum(1 for item in active_queue_items if item['priority_level'] == 2)
    less_urgent_count = sum(1 for item in active_queue_items if item['priority_level'] == 3)
    assessing_count = sum(1 for item in active_queue_items if item['status'] == 'UNDER_ASSESSMENT')

    recent_history = EmergencyPatient.objects.filter(
        status__in=['ADMITTED', 'DISCHARGED', 'TRANSFERRED']
    ).order_by('-updated_at')[:10]

    return render(request, 'emergency_queue.html', {
        'registration_form': registration_form,
        'active_queue': active_queue_items,
        'queue_size': len(active_queue_items),
        'critical_count': critical_count,
        'urgent_count': urgent_count,
        'less_urgent_count': less_urgent_count,
        'assessing_count': assessing_count,
        'recent_history': recent_history,
        'doctors': doctors,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


@login_required
@clinical_staff_required
def emergency_reassess_view(request, patient_id):
    """
    Allows authorized clinical staff to reassess and modify an emergency patient's priority
    with a mandatory clinical justification note.
    Patients are strictly forbidden from calling this view.
    """
    if request.method != 'POST':
        return HttpResponseForbidden("POST request required.")

    patient = get_object_or_404(EmergencyPatient, id=patient_id)
    try:
        new_priority = int(request.POST.get('new_priority'))
        clinical_rationale = request.POST.get('clinical_rationale', '').strip()
    except (TypeError, ValueError):
        messages.error(request, "Invalid priority level submitted.")
        return redirect('emergency_queue_dashboard')

    if not clinical_rationale:
        messages.error(request, "A clinical rationale is mandatory when modifying triage priority.")
        return redirect('emergency_queue_dashboard')

    success, updated_patient, msg = EmergencyPriorityQueue.reassess_priority(
        patient_id=patient.id,
        new_priority=new_priority,
        clinical_rationale=clinical_rationale,
        user=request.user
    )

    if success:
        messages.success(request, f"Clinical priority updated for {patient.patient_code}: {msg}")
    else:
        messages.error(request, f"Failed to update priority: {msg}")

    return redirect('emergency_queue_dashboard')


@login_required
@clinical_staff_required
def emergency_update_status_view(request, patient_id):
    """
    Transitions patient lifecycle status:
    - UNDER_ASSESSMENT (remains in active queue)
    - ADMITTED (removes from active waiting queue)
    - DISCHARGED (removes from active waiting queue)
    - TRANSFERRED (removes from active waiting queue)
    """
    if request.method != 'POST':
        return HttpResponseForbidden("POST request required.")

    patient = get_object_or_404(EmergencyPatient, id=patient_id)
    new_status = request.POST.get('status')
    doctor_id = request.POST.get('doctor_id')

    valid_statuses = dict(EmergencyPatient.STATUS_CHOICES).keys()
    if new_status in valid_statuses:
        patient.status = new_status
        if new_status == 'UNDER_ASSESSMENT' and not patient.assessed_at:
            patient.assessed_at = timezone.now()
        elif new_status in ['ADMITTED', 'DISCHARGED', 'TRANSFERRED']:
            patient.discharged_at = timezone.now()

        if doctor_id:
            try:
                patient.attending_clinician = DoctorProfile.objects.get(id=doctor_id)
            except DoctorProfile.DoesNotExist:
                pass

        patient.save()
        messages.success(request, f"Status for {patient.patient_code} ({patient.full_name}) updated to '{patient.get_status_display()}'.")
    else:
        messages.error(request, "Invalid clinical status specified.")

    return redirect('emergency_queue_dashboard')


@login_required
@clinical_staff_required
def emergency_queue_api(request):
    """
    JSON API delivering real-time queue snapshot reconstructed from database.
    Only authorized staff can access the full clinical queue.
    """
    queue = EmergencyPriorityQueue.get_active_queue_from_db()
    data = queue.get_queue_display_data()
    return JsonResponse({
        'queue': data,
        'count': len(data),
        'timestamp': timezone.now().isoformat(),
    })


def emergency_advisory_view(request):
    """
    Public / Patient Emergency Guidance Page.
    Instructs patients experiencing emergencies not to wait for routine appointments.
    Provides emergency hotline and location.
    Allows authenticated patients to submit an emergency symptom report.
    """
    hospital_name = getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital')
    emergency_phone = getattr(settings, 'HOSPITAL_EMERGENCY_PHONE', '+1 (555) 911-CARE')
    emergency_dept = getattr(settings, 'HOSPITAL_EMERGENCY_DEPARTMENT', 'SmartCare Emergency & Trauma Pavilion, Gate 2')
    hospital_address = getattr(settings, 'DEFAULT_HOSPITAL_ADDRESS', '100 Healthcare Blvd, Metro City')

    form = None
    if request.user.is_authenticated and request.user.is_patient:
        patient_profile = request.user.patient_profile

        if request.method == 'POST':
            form = PatientEmergencyReportForm(request.POST)
            if form.is_valid():
                symptoms = form.cleaned_data['symptoms']
                phone = form.cleaned_data['contact_phone']

                # Create emergency record awaiting in-person clinical triage
                # Patients MUST NOT assign themselves priority! Priority defaults to provisional P2 awaiting triage confirmation.
                emergency_case = EmergencyPatient.objects.create(
                    full_name=request.user.get_full_name() or request.user.username,
                    age=30,
                    contact_number=phone,
                    patient_profile=patient_profile,
                    chief_complaint=f"[Patient Emergency Report] {symptoms}",
                    triage_notes="Self-reported via SmartCare patient portal. Awaiting in-person physiological triage by clinical staff.",
                    priority_level=2,  # Default provisional until clinical staff evaluation
                    status='WAITING'
                )

                messages.warning(
                    request,
                    f"Emergency arrival registered ({emergency_case.patient_code}). "
                    f"Please proceed immediately to {emergency_dept}. Clinical staff will evaluate you on arrival."
                )
                return redirect('patient_emergency_status', emergency_id=emergency_case.id)
        else:
            form = PatientEmergencyReportForm(initial={'contact_phone': request.user.contact_number})

    return render(request, 'emergency_advisory.html', {
        'hospital_name': hospital_name,
        'emergency_phone': emergency_phone,
        'emergency_dept': emergency_dept,
        'hospital_address': hospital_address,
        'form': form
    })


@login_required
def patient_emergency_status_view(request, emergency_id):
    """
    Feature 7: Patient-Visible Emergency Queue Status.
    Strict privacy:
    - Verifies authentication and ensures queue record belongs to patient viewing it.
    - Never exposes other patients' names, symptoms, or medical details.
    - Returns only the patient's own queue position, count of patients ahead, and status.
    """
    emergency_case = get_object_or_404(EmergencyPatient, id=emergency_id)
    user = request.user

    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'admin'

    # Strict ownership verification
    if user.is_patient:
        if not emergency_case.patient_profile or emergency_case.patient_profile.user != user:
            return HttpResponseForbidden("Access Denied: You cannot view another patient's emergency queue record.")
    elif not is_admin and not user.is_clinical_staff:
        return HttpResponseForbidden("Access Denied: You do not have permission to view this emergency record.")

    queue = EmergencyPriorityQueue.get_active_queue_from_db()
    queue_data = queue.get_patient_queue_position(emergency_case.id)

    return render(request, 'patient_emergency_status.html', {
        'emergency_case': emergency_case,
        'queue_data': queue_data,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
        'emergency_dept': getattr(settings, 'HOSPITAL_EMERGENCY_DEPARTMENT', 'SmartCare Emergency & Trauma Pavilion, Gate 2'),
        'emergency_phone': getattr(settings, 'HOSPITAL_EMERGENCY_PHONE', '+1 (555) 911-CARE'),
    })
