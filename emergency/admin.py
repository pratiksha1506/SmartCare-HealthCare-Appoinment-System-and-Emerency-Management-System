from django.contrib import admin
from .models import EmergencyPatient, PriorityAssessmentLog


@admin.register(EmergencyPatient)
class EmergencyPatientAdmin(admin.ModelAdmin):
    list_display = (
        'patient_code',
        'full_name',
        'age',
        'gender',
        'priority_level',
        'status',
        'patient_profile',
        'arrival_time',
        'attending_clinician'
    )
    list_filter = ('priority_level', 'status', 'attending_clinician')
    search_fields = ('patient_code', 'full_name', 'chief_complaint')


@admin.register(PriorityAssessmentLog)
class PriorityAssessmentLogAdmin(admin.ModelAdmin):
    list_display = ('emergency_patient', 'previous_priority', 'new_priority', 'assessed_by', 'timestamp')
    list_filter = ('new_priority', 'timestamp')
