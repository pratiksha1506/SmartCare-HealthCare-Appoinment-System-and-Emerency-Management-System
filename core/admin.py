from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, PatientProfile, DoctorProfile


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('SmartCare Role Info', {'fields': ('role', 'contact_number')}),
    )


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_of_birth', 'gender', 'default_address')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization', 'registration_number', 'consultation_fee', 'is_active', 'available_days')
    list_filter = ('specialization', 'is_active')
    search_fields = ('user__first_name', 'user__last_name', 'registration_number', 'specialization')
