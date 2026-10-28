from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError
from datetime import date, time, timedelta

from core.models import User, PatientProfile, DoctorProfile
from appointments.models import Appointment, ScheduleDisruption, ConsultationRecord
from appointments.forms import AppointmentBookingForm
from emergency.models import EmergencyPatient


class StrictAppointmentFilteringAndAccessTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Doctor A: Dr. Smith
        self.user_doc_a = User.objects.create_user(
            username='dr.smith@smartcare.org',
            email='dr.smith@smartcare.org',
            password='Password123!',
            role='doctor',
            first_name='John',
            last_name='Smith'
        )
        self.doctor_a = DoctorProfile.objects.create(
            user=self.user_doc_a,
            specialization='Cardiology',
            qualification='MD (Cardiology)',
            registration_number='LIC-SMITH-01',
            consultation_fee=500.00,
            available_days='Mon,Tue,Wed,Thu,Fri',
            work_start_time=time(9, 0),
            work_end_time=time(17, 0)
        )

        # Doctor B: Dr. Kumar
        self.user_doc_b = User.objects.create_user(
            username='dr.kumar@smartcare.org',
            email='dr.kumar@smartcare.org',
            password='Password123!',
            role='doctor',
            first_name='Rajesh',
            last_name='Kumar'
        )
        self.doctor_b = DoctorProfile.objects.create(
            user=self.user_doc_b,
            specialization='Neurology',
            qualification='MD (Neurology)',
            registration_number='LIC-KUMAR-02',
            consultation_fee=550.00,
            available_days='Mon,Tue,Wed,Thu,Fri',
            work_start_time=time(9, 0),
            work_end_time=time(17, 0)
        )

        # Patient A: Alice
        self.user_pat_a = User.objects.create_user(
            username='alice@example.com',
            email='alice@example.com',
            password='Password123!',
            role='patient',
            first_name='Alice',
            last_name='Anderson'
        )
        self.patient_a = PatientProfile.objects.create(
            user=self.user_pat_a,
            date_of_birth=date(1990, 5, 10),
            gender='female',
            default_address='10 Pine Road'
        )

        # Patient B: Bob
        self.user_pat_b = User.objects.create_user(
            username='bob@example.com',
            email='bob@example.com',
            password='Password123!',
            role='patient',
            first_name='Bob',
            last_name='Brown'
        )
        self.patient_b = PatientProfile.objects.create(
            user=self.user_pat_b,
            date_of_birth=date(1985, 8, 20),
            gender='male',
            default_address='25 Oak Street'
        )

        # Future appointment date (weekday)
        self.target_date = timezone.localdate() + timedelta(days=2)
        if self.target_date.weekday() >= 5:  # Weekend adjustment
            self.target_date += timedelta(days=2)

        # Appointment 1: Patient A with Doctor A (Dr. Smith)
        self.apt_a = Appointment.objects.create(
            patient=self.patient_a,
            doctor=self.doctor_a,
            appointment_date=self.target_date,
            appointment_time=time(10, 0),
            status='SCHEDULED',
            consultation_reason='heart',
            symptoms_description='Palpitations on exertion'
        )

        # Appointment 2: Patient B with Doctor B (Dr. Kumar)
        self.apt_b = Appointment.objects.create(
            patient=self.patient_b,
            doctor=self.doctor_b,
            appointment_date=self.target_date,
            appointment_time=time(11, 0),
            status='SCHEDULED',
            consultation_reason='neurological',
            symptoms_description='Severe migraine with visual aura'
        )

    def test_1_doctor_a_cannot_see_doctor_b_appointments_on_dashboard(self):
        """
        Requirement 10.1: Doctor A cannot see Doctor B's appointments.
        Dr. Smith logs in. His dashboard must contain Appointment A (his patient Alice),
        and must NOT contain Appointment B (Dr. Kumar's patient Bob).
        """
        self.client.login(username='dr.smith@smartcare.org', password='Password123!')
        response = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(response.status_code, 200)

        # Should see Alice's appointment booked with Dr. Smith
        self.assertContains(response, "Alice Anderson")
        # Must NOT see Bob's appointment booked with Dr. Kumar
        self.assertNotContains(response, "Bob Brown")
        self.assertNotContains(response, "Severe migraine with visual aura")

    def test_2_doctor_a_cannot_access_doctor_b_appointment_by_changing_url(self):
        """
        Requirement 10.2: Doctor A cannot access Doctor B's appointment by changing the URL.
        Dr. Smith attempts to navigate directly to /appointment/<apt_b.id>/.
        Server must reject with 403 Forbidden.
        """
        self.client.login(username='dr.smith@smartcare.org', password='Password123!')
        
        # Accessing own appointment -> 200 OK
        resp_own = self.client.get(reverse('appointment_detail', args=[self.apt_a.id]))
        self.assertEqual(resp_own.status_code, 200)

        # Accessing Doctor B's appointment -> 403 Forbidden
        resp_other = self.client.get(reverse('appointment_detail', args=[self.apt_b.id]))
        self.assertEqual(resp_other.status_code, 403)

        # Attempting to cancel Doctor B's appointment -> 403 Forbidden
        resp_cancel = self.client.get(reverse('cancel_appointment', args=[self.apt_b.id]))
        self.assertEqual(resp_cancel.status_code, 403)

    def test_3_patient_sees_only_their_own_appointments(self):
        """
        Requirement 10.3: A patient sees only their own appointments.
        Alice logs in. Dashboard must show only her booking with Dr. Smith.
        Alice cannot view Bob's appointment detail page (returns 403 Forbidden).
        """
        self.client.login(username='alice@example.com', password='Password123!')
        
        # Dashboard check
        dash_resp = self.client.get(reverse('patient_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, "Dr. John Smith")
        self.assertNotContains(dash_resp, "Dr. Rajesh Kumar")

        # URL tampering check: Alice tries to open Bob's appointment #2
        detail_resp = self.client.get(reverse('appointment_detail', args=[self.apt_b.id]))
        self.assertEqual(detail_resp.status_code, 403)

    def test_7_routine_appointments_remain_separate_from_emergency_cases(self):
        """
        Requirement 10.7: Routine appointments remain separate from emergency cases.
        """
        # Create an emergency case
        emergency = EmergencyPatient.objects.create(
            full_name='Acute Trauma Victim',
            age=50,
            priority_level=1,
            chief_complaint='Severe open fracture with bleeding',
            status='WAITING'
        )

        # Verify emergency case does not appear in Doctor A or Doctor B's routine appointments table
        self.assertEqual(Appointment.objects.filter(patient__user__first_name='Acute Trauma Victim').count(), 0)
        self.assertEqual(Appointment.objects.count(), 2)
        self.assertEqual(EmergencyPatient.objects.count(), 1)

    def test_10_appointment_slots_cannot_be_double_booked(self):
        """
        Requirement 10.10: Appointment slots cannot be double-booked.
        - Server-side form validation prevents booking an already reserved slot.
        - Database UniqueConstraint enforces that (doctor, appointment_date, appointment_time) cannot be duplicated.
        """
        # Form validation check
        form_data = {
            'triage_intent': 'routine',
            'consultation_reason': 'heart',
            'appointment_date': self.target_date.strftime('%Y-%m-%d'),
            'appointment_time': '10:00:00',  # Already booked by Patient A with Doctor A
            'safety_buffer_minutes': 15,
        }
        form = AppointmentBookingForm(doctor=self.doctor_a, patient=self.patient_b, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("already booked", form.errors['__all__'][0])

        # Database constraint check
        with self.assertRaises(IntegrityError):
            Appointment.objects.create(
                patient=self.patient_b,
                doctor=self.doctor_a,
                appointment_date=self.target_date,
                appointment_time=time(10, 0),
                status='SCHEDULED'
            )


class HospitalManagementWorkflowTests(TestCase):
    """
    Test suite verifying the complete Administrator, Doctor, and Patient management workflow:
    1. Administrator creates doctor account.
    2. New doctor logs in successfully.
    3. Doctor A cannot access Doctor B's appointments.
    4. Doctor can access patient record for assigned appointment.
    5. Doctor cannot access unrelated patient's private medical record (403 Forbidden).
    6. Doctor can save consultation notes (diagnosis, plan, prescription).
    7. Consultation history is preserved across visits.
    8. Patient can view only their own records and consultation notes.
    9. Ordinary doctor or patient cannot create another doctor account (403 Forbidden).
    10. Unauthorized users cannot modify appointment or consultation records.
    """

    def setUp(self):
        self.client = Client()

        # 1. Administrator
        self.admin = User.objects.create_user(
            username='hospital.admin@smartcare.org',
            email='hospital.admin@smartcare.org',
            password='AdminPassword123!',
            role='admin',
            is_staff=True,
            is_superuser=True
        )

        # 2. Doctor A (Dr. Smith - Cardiology)
        self.user_doc_a = User.objects.create_user(
            username='dr.smith@smartcare.org',
            email='dr.smith@smartcare.org',
            password='DocPassword123!',
            role='doctor',
            first_name='John',
            last_name='Smith'
        )
        self.doctor_a = DoctorProfile.objects.create(
            user=self.user_doc_a,
            specialization='Cardiology',
            qualification='MD (Cardiology)',
            registration_number='LIC-SMITH-001',
            consultation_fee=500.00,
            available_days='Mon,Tue,Wed,Thu,Fri',
            work_start_time=time(9, 0),
            work_end_time=time(17, 0),
            is_active=True
        )

        # 3. Doctor B (Dr. Kumar - Neurology)
        self.user_doc_b = User.objects.create_user(
            username='dr.kumar@smartcare.org',
            email='dr.kumar@smartcare.org',
            password='DocPassword123!',
            role='doctor',
            first_name='Rajesh',
            last_name='Kumar'
        )
        self.doctor_b = DoctorProfile.objects.create(
            user=self.user_doc_b,
            specialization='Neurology',
            qualification='MD (Neurology)',
            registration_number='LIC-KUMAR-002',
            consultation_fee=550.00,
            available_days='Mon,Tue,Wed,Thu,Fri',
            work_start_time=time(9, 0),
            work_end_time=time(17, 0),
            is_active=True
        )

        # 4. Patient A (Alice)
        self.user_pat_a = User.objects.create_user(
            username='alice@example.com',
            email='alice@example.com',
            password='PatientPass123!',
            role='patient',
            first_name='Alice',
            last_name='Anderson',
            contact_number='+1 555-0101'
        )
        self.patient_a = PatientProfile.objects.create(
            user=self.user_pat_a,
            date_of_birth=date(1990, 5, 10),
            gender='female',
            default_address='10 Pine Road',
            medical_history='Mild asthma; allergic to penicillin'
        )

        # 5. Patient B (Bob)
        self.user_pat_b = User.objects.create_user(
            username='bob@example.com',
            email='bob@example.com',
            password='PatientPass123!',
            role='patient',
            first_name='Bob',
            last_name='Brown',
            contact_number='+1 555-0202'
        )
        self.patient_b = PatientProfile.objects.create(
            user=self.user_pat_b,
            date_of_birth=date(1985, 8, 20),
            gender='male',
            default_address='25 Oak Street',
            medical_history='Type 2 Diabetes, hypertension'
        )

        # Target date
        self.target_date = timezone.localdate() + timedelta(days=2)
        if self.target_date.weekday() >= 5:
            self.target_date += timedelta(days=2)

        # Appointment 1: Patient A with Doctor A
        self.apt_a = Appointment.objects.create(
            patient=self.patient_a,
            doctor=self.doctor_a,
            appointment_date=self.target_date,
            appointment_time=time(10, 0),
            status='SCHEDULED',
            consultation_reason='heart',
            symptoms_description='Palpitations and shortness of breath'
        )

        # Appointment 2: Patient B with Doctor B
        self.apt_b = Appointment.objects.create(
            patient=self.patient_b,
            doctor=self.doctor_b,
            appointment_date=self.target_date,
            appointment_time=time(11, 0),
            status='SCHEDULED',
            consultation_reason='neurological',
            symptoms_description='Frequent migraines with aura'
        )

    def test_case_1_administrator_can_successfully_create_doctor_account(self):
        """
        Test 1: Administrator can successfully create a doctor account.
        Checks User, DoctorProfile, specialization, registration number, and duplicate validations.
        """
        self.client.login(username='hospital.admin@smartcare.org', password='AdminPassword123!')

        # Valid creation
        doc_data = {
            'full_name': 'Dr. Elena Rostova',
            'email': 'elena.rostova@smartcare.org',
            'password': 'TempPassword2026!',
            'confirm_password': 'TempPassword2026!',
            'specialization': 'Dermatology',
            'qualification': 'MD (Dermatology), Board Certified',
            'registration_number': 'REG-DERM-7788',
            'experience_years': 7,
            'consultation_fee': '480.00',
            'contact_number': '+1 555-7788',
            'available_days_list': ['Mon', 'Wed', 'Fri'],
            'work_start_time': '09:00:00',
            'work_end_time': '16:00:00',
            'slot_duration_minutes': 30,
            'is_active': True,
        }
        response = self.client.post(reverse('admin_doctor_create'), doc_data)
        self.assertEqual(response.status_code, 302)

        # Doctor user and profile exist
        doc_user = User.objects.get(email='elena.rostova@smartcare.org')
        self.assertEqual(doc_user.role, 'doctor')
        self.assertTrue(doc_user.is_doctor)
        self.assertTrue(doc_user.check_password('TempPassword2026!'))
        self.assertEqual(doc_user.doctor_profile.specialization, 'Dermatology')
        self.assertEqual(doc_user.doctor_profile.registration_number, 'REG-DERM-7788')
        self.assertEqual(doc_user.doctor_profile.available_days, 'Mon,Wed,Fri')

        # Test duplicate email rejected
        dup_email_data = dict(doc_data)
        dup_email_data['registration_number'] = 'REG-DIFF-9999'
        resp_dup_email = self.client.post(reverse('admin_doctor_create'), dup_email_data)
        self.assertEqual(resp_dup_email.status_code, 200)
        self.assertContains(resp_dup_email, "already exists")

        # Test duplicate registration number rejected
        dup_reg_data = dict(doc_data)
        dup_reg_data['email'] = 'different.doc@smartcare.org'
        resp_dup_reg = self.client.post(reverse('admin_doctor_create'), dup_reg_data)
        self.assertEqual(resp_dup_reg.status_code, 200)
        self.assertContains(resp_dup_reg, "already exists")

    def test_case_2_newly_created_doctor_can_log_in_using_their_credentials(self):
        """
        Test 2: The newly created doctor can log in using their credentials,
        and is routed to their doctor dashboard showing their name and specialization.
        """
        # Create doctor account via User / DoctorProfile
        new_doc_user = User.objects.create_user(
            username='claire.danvers@smartcare.org',
            email='claire.danvers@smartcare.org',
            password='ClairePass2026!',
            role='doctor',
            first_name='Claire',
            last_name='Danvers'
        )
        DoctorProfile.objects.create(
            user=new_doc_user,
            specialization='Pediatrics',
            qualification='MD (Pediatrics)',
            registration_number='LIC-PED-3344',
            consultation_fee=400.00,
            available_days='Mon,Tue,Wed,Thu,Fri',
            work_start_time=time(9, 0),
            work_end_time=time(17, 0)
        )

        # Doctor logs in
        login_resp = self.client.post(reverse('login'), {
            'email': 'claire.danvers@smartcare.org',
            'password': 'ClairePass2026!'
        })
        self.assertEqual(login_resp.status_code, 302)

        # Redirects to dashboard
        dash_resp = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, "Dr. Claire Danvers")
        self.assertContains(dash_resp, "Pediatrics")

        # Test doctor logging in when next was /register/doctor/ does NOT redirect to registration
        self.client.logout()
        login_with_next = self.client.post(reverse('login') + '?next=/register/doctor/', {
            'email': 'claire.danvers@smartcare.org',
            'password': 'ClairePass2026!'
        })
        self.assertEqual(login_with_next.status_code, 302)
        self.assertNotEqual(login_with_next.url, '/register/doctor/')
        self.assertIn('dashboard', login_with_next.url)

    def test_case_3_doctor_a_cannot_view_doctor_b_appointments(self):
        """
        Test 3: Doctor A cannot view Doctor B's appointments.
        Dr. Smith logs in. Cannot see Dr. Kumar's appointment on the dashboard or via direct URL.
        """
        self.client.login(username='dr.smith@smartcare.org', password='DocPassword123!')

        # Dashboard check
        dash_resp = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, "Alice Anderson")
        self.assertNotContains(dash_resp, "Bob Brown")

        # URL tampering: Doctor A tries to access Doctor B's appointment detail
        tamper_resp = self.client.get(reverse('appointment_detail', args=[self.apt_b.id]))
        self.assertEqual(tamper_resp.status_code, 403)

    def test_case_4_doctor_can_open_patient_record_through_assigned_appointment(self):
        """
        Test 4: Doctor can open a patient's record through an appointment assigned to that doctor.
        Displays patient demographic, reason for consultation, reported symptoms, and medical history.
        """
        self.client.login(username='dr.smith@smartcare.org', password='DocPassword123!')

        resp = self.client.get(reverse('doctor_consultation', args=[self.apt_a.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Alice Anderson")
        self.assertContains(resp, "+1 555-0101")
        self.assertContains(resp, "Palpitations and shortness of breath")
        self.assertContains(resp, "Mild asthma; allergic to penicillin")

    def test_case_5_doctor_cannot_open_unrelated_patient_private_medical_record(self):
        """
        Test 5: Doctor cannot open an unrelated patient's private medical record (403 Forbidden).
        Dr. Smith attempts to open Dr. Kumar's appointment consultation.
        """
        self.client.login(username='dr.smith@smartcare.org', password='DocPassword123!')

        # Dr. Smith tries to open Bob's consultation through appointment B
        resp = self.client.get(reverse('doctor_consultation', args=[self.apt_b.id]))
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Access Denied", resp.content.decode())

        # Dr. Smith tries to access Bob's medical record directly by guessing patient ID
        direct_resp = self.client.get(reverse('doctor_patient_record', args=[self.patient_b.id]))
        self.assertEqual(direct_resp.status_code, 403)
        self.assertIn("Access Denied", direct_resp.content.decode())

    def test_case_6_doctor_can_save_consultation_notes_diagnosis_treatment_and_prescriptions(self):
        """
        Test 6: Doctor can save consultation notes, diagnosis, treatment plan, and prescriptions
        for a completed appointment.
        """
        self.client.login(username='dr.smith@smartcare.org', password='DocPassword123!')

        post_data = {
            'clinical_notes': 'Vitals: BP 118/76, HR 74, SpO2 99%. Regular rate and rhythm.',
            'diagnosis': 'Benign Premature Ventricular Contractions (PVCs)',
            'treatment_plan': 'Reassurance, avoid stimulant energy drinks, regular cardiovascular exercise.',
            'prescribed_medications': 'Bisoprolol 2.5mg PO once daily in morning x 30 days',
            'follow_up_instructions': 'Return in 4 weeks for repeat 24h Holter monitoring.',
            'follow_up_date': (timezone.localdate() + timedelta(days=28)).strftime('%Y-%m-%d'),
            'appointment_status': 'COMPLETED',
            'patient_medical_history': 'Mild asthma; allergic to penicillin; non-smoker',
        }
        resp = self.client.post(reverse('doctor_consultation', args=[self.apt_a.id]), post_data)
        self.assertEqual(resp.status_code, 302)

        # Verify database update
        self.apt_a.refresh_from_db()
        self.assertEqual(self.apt_a.status, 'COMPLETED')

        record = ConsultationRecord.objects.get(appointment=self.apt_a)
        self.assertEqual(record.diagnosis, 'Benign Premature Ventricular Contractions (PVCs)')
        self.assertEqual(record.prescribed_medications, 'Bisoprolol 2.5mg PO once daily in morning x 30 days')
        self.assertEqual(record.doctor, self.doctor_a)
        self.assertEqual(record.patient, self.patient_a)

        # Check updated medical history
        self.patient_a.refresh_from_db()
        self.assertIn('non-smoker', self.patient_a.medical_history)

    def test_case_7_consultation_history_is_preserved_across_visits(self):
        """
        Test 7: Consultation history is preserved across visits and displayed when reviewing returning patients.
        """
        # First visit: record consultation
        ConsultationRecord.objects.create(
            appointment=self.apt_a,
            patient=self.patient_a,
            doctor=self.doctor_a,
            clinical_notes='First visit initial exam',
            diagnosis='Initial Episode: PVCs',
            prescribed_medications='Bisoprolol 2.5mg PO daily',
            treatment_plan='Initial cardiac workup'
        )
        self.apt_a.status = 'COMPLETED'
        self.apt_a.save()

        # Returning patient: Create second visit appointment 3 weeks later
        apt_second_visit = Appointment.objects.create(
            patient=self.patient_a,
            doctor=self.doctor_a,
            appointment_date=self.target_date + timedelta(days=21),
            appointment_time=time(14, 0),
            status='SCHEDULED',
            consultation_reason='heart',
            symptoms_description='Follow-up check on PVCs'
        )

        # Doctor opens second visit consultation
        self.client.login(username='dr.smith@smartcare.org', password='DocPassword123!')
        resp = self.client.get(reverse('doctor_consultation', args=[apt_second_visit.id]))
        self.assertEqual(resp.status_code, 200)

        # Historical diagnosis and prescription are displayed
        self.assertContains(resp, "Initial Episode: PVCs")
        self.assertContains(resp, "Bisoprolol 2.5mg PO daily")

    def test_case_8_patient_can_view_only_their_own_records_and_consultation_notes(self):
        """
        Test 8: Patient can view only their own records and consultation notes.
        Alice can view her completed appointment and prescription, but cannot view Bob's appointment.
        """
        # Create consultation record for Alice
        ConsultationRecord.objects.create(
            appointment=self.apt_a,
            patient=self.patient_a,
            doctor=self.doctor_a,
            diagnosis='Benign Arrhythmia',
            prescribed_medications='Metoprolol 25mg PO once daily',
            treatment_plan='Hydration and regular sleep schedule'
        )
        self.apt_a.status = 'COMPLETED'
        self.apt_a.save()

        # Alice logs in
        self.client.login(username='alice@example.com', password='PatientPass123!')

        # Patient dashboard displays her diagnosis
        dash_resp = self.client.get(reverse('patient_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, "Benign Arrhythmia")

        # Patient detail page displays prescription
        detail_resp = self.client.get(reverse('appointment_detail', args=[self.apt_a.id]))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, "Metoprolol 25mg PO once daily")

        # Alice cannot view Bob's appointment detail
        resp_bob = self.client.get(reverse('appointment_detail', args=[self.apt_b.id]))
        self.assertEqual(resp_bob.status_code, 403)

        # Alice cannot access doctor consultation editor
        resp_consult = self.client.get(reverse('doctor_consultation', args=[self.apt_a.id]))
        self.assertEqual(resp_consult.status_code, 403)

    def test_case_9_ordinary_doctors_and_patients_cannot_create_doctor_accounts(self):
        """
        Test 9: Ordinary doctor or patient cannot create another doctor account (403 Forbidden).
        """
        # Doctor attempt
        self.client.login(username='dr.smith@smartcare.org', password='DocPassword123!')
        doc_resp_get = self.client.get(reverse('admin_doctor_create'))
        self.assertEqual(doc_resp_get.status_code, 403)

        doc_resp_post = self.client.post(reverse('admin_doctor_create'), {
            'full_name': 'Dr. Rogue',
            'email': 'rogue@hospital.com',
            'password': 'Password123!',
        })
        self.assertEqual(doc_resp_post.status_code, 403)

        # Patient attempt
        self.client.login(username='alice@example.com', password='PatientPass123!')
        pat_resp_get = self.client.get(reverse('admin_doctor_create'))
        self.assertEqual(pat_resp_get.status_code, 403)

        # Public doctor self-registration is also disabled
        pub_resp = self.client.get(reverse('doctor_register'))
        self.assertEqual(pub_resp.status_code, 403)

    def test_case_10_unauthorized_users_cannot_modify_appointment_or_consultation_records(self):
        """
        Test 10: Unauthorized users cannot modify appointment or consultation records.
        """
        # Doctor B attempts to modify Doctor A's appointment consultation notes
        self.client.login(username='dr.kumar@smartcare.org', password='DocPassword123!')
        hacker_post = self.client.post(reverse('doctor_consultation', args=[self.apt_a.id]), {
            'clinical_notes': 'Malicious modification attempt',
            'diagnosis': 'Fake diagnosis',
            'treatment_plan': 'None',
        })
        self.assertEqual(hacker_post.status_code, 403)

        # Doctor B attempts to modify Doctor A's appointment status
        hacker_status = self.client.post(reverse('update_appointment_status', args=[self.apt_a.id]), {
            'status': 'COMPLETED'
        })
        self.assertEqual(hacker_status.status_code, 403)

        # Doctor B attempts to cancel Doctor A's appointment
        hacker_cancel = self.client.post(reverse('cancel_appointment', args=[self.apt_a.id]))
        self.assertEqual(hacker_cancel.status_code, 403)

        # Patient B attempts to cancel Patient A's appointment
        self.client.login(username='bob@example.com', password='PatientPass123!')
        pat_cancel = self.client.post(reverse('cancel_appointment', args=[self.apt_a.id]))
        self.assertEqual(pat_cancel.status_code, 403)

        # Appointment status remains SCHEDULED
        self.apt_a.refresh_from_db()
        self.assertEqual(self.apt_a.status, 'SCHEDULED')
        self.assertFalse(ConsultationRecord.objects.filter(appointment=self.apt_a).exists())
