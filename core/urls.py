from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/patient/', views.patient_register_view, name='patient_register'),
    path('register/doctor/', views.doctor_register_view, name='doctor_register'),
    path('login/', views.login_view, name='login'),
    path('login/patient/', views.patient_login_view, name='patient_login'),
    path('login/doctor/', views.doctor_login_view, name='doctor_login'),
    path('login/admin/', views.admin_login_view, name='admin_login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_redirect_view, name='dashboard_redirect'),
    
    # Hospital Administrator Doctor & Hospital Management
    path('administrator/dashboard/', views.admin_doctor_list_view, name='administrator_dashboard'),
    path('hospital/doctors/', views.admin_doctor_list_view, name='admin_doctor_list'),
    path('hospital/doctors/add/', views.admin_doctor_create_view, name='admin_doctor_create'),
    path('hospital/doctors/<int:doctor_id>/', views.admin_doctor_detail_view, name='admin_doctor_detail'),
    path('hospital/doctors/<int:doctor_id>/edit/', views.admin_doctor_edit_view, name='admin_doctor_edit'),
    path('hospital/doctors/<int:doctor_id>/reset-password/', views.admin_doctor_password_reset_view, name='admin_doctor_password_reset'),
    path('hospital/doctors/<int:doctor_id>/toggle/', views.admin_doctor_toggle_status_view, name='admin_doctor_toggle_status'),
    path('hospital/admin/patients/', views.admin_patient_list_view, name='admin_patient_list'),
    path('hospital/admin/appointments/', views.admin_appointment_list_view, name='admin_appointment_list'),
    path('admin-dashboard/', views.admin_doctor_list_view, name='admin_dashboard'),
    path('hospital/admin/', views.admin_doctor_list_view, name='hospital_admin'),

    # Doctor Self Availability Management
    path('doctor/availability/', views.doctor_manage_availability_view, name='doctor_availability'),
]
