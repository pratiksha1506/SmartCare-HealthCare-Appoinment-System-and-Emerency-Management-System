from django.urls import path
from . import views

urlpatterns = [
    path('find-doctors/', views.find_doctors_view, name='find_doctors'),
    path('book/<int:doctor_id>/', views.book_appointment_view, name='book_appointment'),
    path('patient/dashboard/', views.patient_dashboard_view, name='patient_dashboard'),
    path('doctor/dashboard/', views.doctor_dashboard_view, name='doctor_dashboard'),
    path('appointment/<int:appointment_id>/', views.appointment_detail_view, name='appointment_detail'),
    path('appointment/<int:appointment_id>/cancel/', views.cancel_appointment_view, name='cancel_appointment'),
    path('appointment/<int:appointment_id>/status/', views.update_appointment_status_view, name='update_appointment_status'),
    path('appointment/<int:appointment_id>/check-in/', views.check_in_appointment_view, name='check_in_appointment'),
    path('doctor/consultation/<int:appointment_id>/', views.doctor_consultation_view, name='doctor_consultation'),
    path('doctor/patient/<int:patient_id>/record/', views.doctor_patient_record_view, name='doctor_patient_record'),
    path('doctor/disruption/record/', views.record_disruption_view, name='record_disruption'),
    
    # API endpoints
    path('api/available-slots/', views.get_available_slots_api, name='api_available_slots'),
]
