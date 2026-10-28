from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.http import HttpResponseForbidden
from django.conf import settings

from .forms import (
    PatientRegistrationForm,
    AdminDoctorCreationForm,
    AdminDoctorEditForm,
    AdminDoctorPasswordResetForm,
    DoctorAvailabilityForm,
    LoginForm,
    RoleLoginForm
)
from .models import DoctorProfile, PatientProfile, User


def patient_required(view_func):
    """Restricts access exclusively to registered patients."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_patient:
            messages.error(request, "Access restricted: This area is reserved for registered patients.")
            return redirect('dashboard_redirect')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def doctor_required(view_func):
    """Restricts access to registered doctors."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_doctor:
            messages.error(request, "Access restricted: This area is reserved for medical clinicians.")
            return redirect('dashboard_redirect')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    """Restricts access strictly to authorized hospital administrators."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (request.user.is_admin or request.user.is_superuser or request.user.is_staff):
            return HttpResponseForbidden("Access Denied: Only authorized hospital administrators can perform this action.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def clinical_staff_required(view_func):
    """Restricts access to clinical staff, triage nurses, or hospital administrators."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (request.user.is_clinical_staff or request.user.is_admin):
            return HttpResponseForbidden("Access Denied: Authorized clinical staff credentials required.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def home_view(request):
    featured_doctors = DoctorProfile.objects.filter(is_active=True).select_related('user').all()[:6]
    specializations = [s[0] for s in DoctorProfile.SPECIALIZATION_CHOICES]
    return render(request, 'home.html', {
        'featured_doctors': featured_doctors,
        'specializations': specializations,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
        'hospital_address': getattr(settings, 'DEFAULT_HOSPITAL_ADDRESS', '100 Healthcare Blvd, Metro City'),
    })


def patient_register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to SmartCare, {user.first_name}! Your patient profile is active.")
            return redirect('patient_dashboard')
    else:
        form = PatientRegistrationForm()

    return render(request, 'patient_register.html', {'form': form})


def doctor_register_view(request):
    """
    Public doctor self-registration is disabled.
    Only authorized administrators can add doctors.
    """
    if request.user.is_authenticated and (request.user.is_admin or request.user.is_superuser or request.user.is_staff):
        return redirect('admin_doctor_create')

    return render(
        request,
        'doctor_register_denied.html',
        {
            'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
        },
        status=403
    )


@login_required
@admin_required
def admin_doctor_list_view(request):
    """
    Hospital Administrator dashboard to manage doctors.
    """
    doctors = DoctorProfile.objects.select_related('user').order_by('user__first_name')
    return render(request, 'admin_doctor_list.html', {
        'doctors': doctors,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


@login_required
@admin_required
def admin_doctor_create_view(request):
    """
    Allows hospital administrator to onboard a new doctor profile and account.
    """
    if request.method == 'POST':
        form = AdminDoctorCreationForm(request.POST)
        if form.is_valid():
            doc_user = form.save()
            messages.success(
                request,
                f"Doctor account for Dr. {doc_user.get_full_name()} ({doc_user.doctor_profile.specialization}) "
                f"has been created successfully. The doctor can now log in using {doc_user.email}."
            )
            return redirect('admin_doctor_list')
        else:
            messages.error(request, "Failed to create doctor account. Please review and correct the errors below.")
    else:
        form = AdminDoctorCreationForm()

    return render(request, 'admin_doctor_create.html', {'form': form})


@login_required
@admin_required
def admin_doctor_detail_view(request, doctor_id):
    """
    Hospital Administrator views full details, schedule, and appointments for a doctor.
    """
    from appointments.models import Appointment
    doctor = get_object_or_404(DoctorProfile.objects.select_related('user'), id=doctor_id)
    appointments = Appointment.objects.filter(doctor=doctor).select_related(
        'patient', 'patient__user'
    ).order_by('-appointment_date', '-appointment_time')[:30]

    return render(request, 'admin_doctor_detail.html', {
        'doctor': doctor,
        'appointments': appointments,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


@login_required
@admin_required
def admin_doctor_toggle_status_view(request, doctor_id):
    """
    Toggles doctor active/inactive status.
    """
    if request.method != 'POST':
        return HttpResponseForbidden("POST request required.")

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    doctor.is_active = not doctor.is_active
    doctor.save()
    status_label = "Activated" if doctor.is_active else "Deactivated"
    messages.info(request, f"Dr. {doctor.user.get_full_name()} has been {status_label}.")
    return redirect('admin_doctor_list')


@login_required
@admin_required
def admin_doctor_edit_view(request, doctor_id):
    """
    Hospital Administrator edits doctor profile, specialization, fee, days, hours, slots, active status.
    """
    doctor = get_object_or_404(DoctorProfile.objects.select_related('user'), id=doctor_id)
    if request.method == 'POST':
        form = AdminDoctorEditForm(request.POST, instance=doctor)
        if form.is_valid():
            form.save()
            messages.success(request, f"Doctor profile for Dr. {doctor.user.get_full_name()} has been updated successfully.")
            return redirect('admin_doctor_list')
    else:
        form = AdminDoctorEditForm(instance=doctor)

    return render(request, 'admin_doctor_edit.html', {
        'form': form,
        'doctor': doctor,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


@login_required
@admin_required
def admin_doctor_password_reset_view(request, doctor_id):
    """
    Hospital Administrator resets or sets a temporary password for a doctor.
    """
    doctor = get_object_or_404(DoctorProfile.objects.select_related('user'), id=doctor_id)
    if request.method == 'POST':
        form = AdminDoctorPasswordResetForm(request.POST)
        if form.is_valid():
            form.save(doctor.user)
            messages.success(request, f"Password for Dr. {doctor.user.get_full_name()} ({doctor.user.email}) has been reset successfully.")
            return redirect('admin_doctor_list')
    else:
        form = AdminDoctorPasswordResetForm()

    return render(request, 'admin_doctor_reset_password.html', {
        'form': form,
        'doctor': doctor,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


@login_required
@admin_required
def admin_patient_list_view(request):
    """
    Hospital Administrator views and manages patient accounts.
    """
    from django.db.models import Count
    patients = PatientProfile.objects.select_related('user').annotate(
        appointment_count=Count('appointments')
    ).order_by('-created_at')

    return render(request, 'admin_patient_list.html', {
        'patients': patients,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


@login_required
@admin_required
def admin_appointment_list_view(request):
    """
    Hospital Administrator views all appointments across all hospital doctors and patients.
    """
    from appointments.models import Appointment
    doctor_id = request.GET.get('doctor_id')
    status_filter = request.GET.get('status')
    date_filter = request.GET.get('date')

    appointments = Appointment.objects.select_related(
        'doctor', 'doctor__user', 'patient', 'patient__user'
    ).order_by('-appointment_date', '-appointment_time')

    if doctor_id:
        appointments = appointments.filter(doctor_id=doctor_id)
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if date_filter:
        appointments = appointments.filter(appointment_date=date_filter)

    doctors = DoctorProfile.objects.select_related('user').order_by('user__first_name')
    statuses = Appointment.STATUS_CHOICES

    return render(request, 'admin_appointment_list.html', {
        'appointments': appointments,
        'doctors': doctors,
        'statuses': statuses,
        'selected_doctor': doctor_id,
        'selected_status': status_filter,
        'selected_date': date_filter,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


@login_required
@doctor_required
def doctor_manage_availability_view(request):
    """
    Allows doctors to update their consultation days, hours, slot durations, and active status.
    """
    doctor = request.user.doctor_profile

    if request.method == 'POST':
        form = DoctorAvailabilityForm(request.POST, instance=doctor)
        if form.is_valid():
            form.save()
            messages.success(request, "Your consultation availability schedule has been updated.")
            return redirect('doctor_dashboard')
    else:
        form = DoctorAvailabilityForm(instance=doctor)

    return render(request, 'doctor_availability.html', {
        'form': form,
        'doctor': doctor
    })


def patient_login_view(request):
    """
    Dedicated login endpoint for patients.
    Validates patient role and redirects to patient dashboard.
    """
    if request.user.is_authenticated:
        if request.user.is_patient:
            return redirect('patient_dashboard')
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = RoleLoginForm(request.POST, target_role='patient')
        if form.is_valid():
            user = form.user
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.first_name}!")
            return redirect('patient_dashboard')
        else:
            messages.error(request, "Patient sign-in failed. Please verify your credentials.")
    else:
        form = RoleLoginForm(target_role='patient')

    return render(request, 'login_role.html', {
        'form': form,
        'portal_role': 'patient',
        'portal_title': 'Patient Portal Sign In',
        'portal_badge': '👤 Patient Access',
        'portal_description': 'Sign in to book doctor appointments, track departure alerts, and manage scheduled consultations.',
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


def doctor_login_view(request):
    """
    Dedicated login endpoint for hospital doctors.
    Validates doctor role and active status, then redirects to doctor dashboard.
    """
    if request.user.is_authenticated:
        if request.user.is_doctor:
            return redirect('doctor_dashboard')
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = RoleLoginForm(request.POST, target_role='doctor')
        if form.is_valid():
            user = form.user
            login(request, user)
            messages.success(request, f"Welcome back, Dr. {user.get_full_name() or user.last_name}!")
            return redirect('doctor_dashboard')
        else:
            messages.error(request, "Doctor sign-in failed. Please verify your credentials.")
    else:
        form = RoleLoginForm(target_role='doctor')

    return render(request, 'login_role.html', {
        'form': form,
        'portal_role': 'doctor',
        'portal_title': 'Doctor Portal Sign In',
        'portal_badge': '🩺 Clinician Access',
        'portal_description': 'Sign in with the professional credentials issued by the Hospital Administrator to access daily appointments and clinical records.',
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


def admin_login_view(request):
    """
    Dedicated login endpoint for hospital administrators.
    Validates administrator permissions and redirects to administrator dashboard.
    """
    if request.user.is_authenticated:
        if request.user.is_admin or request.user.is_staff or request.user.is_superuser:
            return redirect('administrator_dashboard')
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = RoleLoginForm(request.POST, target_role='admin')
        if form.is_valid():
            user = form.user
            login(request, user)
            messages.success(request, f"Welcome back, Administrator {user.get_full_name() or user.username}!")
            return redirect('administrator_dashboard')
        else:
            messages.error(request, "Administrator sign-in failed. Please verify your credentials.")
    else:
        form = RoleLoginForm(target_role='admin')

    return render(request, 'login_role.html', {
        'form': form,
        'portal_role': 'admin',
        'portal_title': 'Hospital Administrator Sign In',
        'portal_badge': '🏥 Administrator Access',
        'portal_description': 'Sign in to access the hospital administrative console, onboard physicians, and oversee operations.',
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.user
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            next_url = request.GET.get('next', '').strip()
            if next_url and next_url not in ['/register/doctor/', '/register/doctor', '/register/patient/', '/register/patient']:
                return redirect(next_url)
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Sign-in failed. Please check your credentials.")
    else:
        form = LoginForm()

    return render(request, 'login.html', {
        'form': form,
        'hospital_name': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
    })


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out securely.")
    return redirect('home')


@login_required
def dashboard_redirect_view(request):
    user = request.user
    if user.is_patient:
        return redirect('patient_dashboard')
    elif user.is_doctor:
        return redirect('doctor_dashboard')
    elif user.is_admin or user.is_superuser or user.is_staff:
        return redirect('administrator_dashboard')
    return redirect('home')
