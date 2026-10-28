from django.contrib import admin
from .models import Appointment, ScheduleDisruption, ConsultationRecord


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'patient',
        'doctor',
        'appointment_date',
        'appointment_time',
        'consultation_reason',
        'status',
        'estimated_travel_duration_minutes',
        'recommended_departure_time',
        'delayed_by_minutes'
    )
    list_filter = ('status', 'consultation_reason', 'appointment_date', 'doctor')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'doctor__user__first_name', 'symptoms_description', 'health_concern')


@admin.register(ScheduleDisruption)
class ScheduleDisruptionAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'disruption_date', 'start_time', 'delay_minutes', 'recorded_by', 'created_at')
    list_filter = ('disruption_date', 'doctor')


@admin.register(ConsultationRecord)
class ConsultationRecordAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'patient', 'doctor', 'diagnosis', 'created_at')
    list_filter = ('doctor', 'created_at')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'diagnosis', 'prescribed_medications')
