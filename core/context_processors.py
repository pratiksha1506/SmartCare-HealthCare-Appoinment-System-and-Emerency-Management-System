from django.conf import settings


def smartcare_global_context(request):
    """Provides common hospital variables across all templates."""
    user = request.user
    role = None
    profile = None
    is_admin = False
    is_staff = False

    if user.is_authenticated:
        role = getattr(user, 'role', 'patient')
        is_admin = getattr(user, 'is_admin', False) or user.is_superuser or user.is_staff or role == 'admin'
        is_staff = getattr(user, 'is_clinical_staff', False) or is_admin
        if role == 'patient' and hasattr(user, 'patient_profile'):
            profile = user.patient_profile
        elif role == 'doctor' and hasattr(user, 'doctor_profile'):
            profile = user.doctor_profile

    return {
        'APP_NAME': 'SmartCare',
        'ROUTING_PROVIDER': getattr(settings, 'ROUTING_PROVIDER', 'simulation'),
        'IS_SIMULATION_MODE': getattr(settings, 'ROUTING_PROVIDER', 'simulation') == 'simulation',
        'DEFAULT_HOSPITAL_NAME': getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
        'DEFAULT_HOSPITAL_ADDRESS': getattr(settings, 'DEFAULT_HOSPITAL_ADDRESS', '100 Healthcare Blvd, Metro City'),
        'HOSPITAL_EMERGENCY_PHONE': getattr(settings, 'HOSPITAL_EMERGENCY_PHONE', '+1 (555) 911-CARE'),
        'HOSPITAL_EMERGENCY_DEPARTMENT': getattr(settings, 'HOSPITAL_EMERGENCY_DEPARTMENT', 'SmartCare Emergency & Trauma Pavilion, Gate 2'),
        'DEFAULT_SAFETY_BUFFER_MINUTES': getattr(settings, 'DEFAULT_SAFETY_BUFFER_MINUTES', 15),
        'user_role': role,
        'user_profile': profile,
        'is_hospital_admin': is_admin,
        'is_clinical_staff': is_staff,
    }
