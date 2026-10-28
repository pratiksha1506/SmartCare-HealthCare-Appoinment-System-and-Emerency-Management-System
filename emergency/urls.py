from django.urls import path
from . import views

urlpatterns = [
    path('emergency/queue/', views.emergency_queue_dashboard_view, name='emergency_queue_dashboard'),
    path('emergency/patient/<int:patient_id>/reassess/', views.emergency_reassess_view, name='emergency_reassess'),
    path('emergency/patient/<int:patient_id>/status/', views.emergency_update_status_view, name='emergency_update_status'),
    path('api/emergency/queue/', views.emergency_queue_api, name='api_emergency_queue'),
    
    # Patient Emergency Reporting and Status Tracking
    path('emergency/advisory/', views.emergency_advisory_view, name='emergency_advisory'),
    path('emergency/my-status/<int:emergency_id>/', views.patient_emergency_status_view, name='patient_emergency_status'),
]
