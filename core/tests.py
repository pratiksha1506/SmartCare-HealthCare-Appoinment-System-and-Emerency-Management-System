from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from datetime import date
from core.models import User, PatientProfile, DoctorProfile


class AuthenticationAndRegistrationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin = User.objects.create_user(
            username='hospital.admin@smartcare.org',
            email='hospital.admin@smartcare.org',
            password='AdminPassword123!',
            role='admin',
            is_staff=True,
            is_superuser=True
        )

        # Patient user
        self.patient_user = User.objects.create_user(
            username='pat.test@smartcare.org',
            email='pat.test@smartcare.org',
            password='PatientPass123!',
            role='patient'
        )
        self.patient_profile = PatientProfile.objects.create(
            user=self.patient_user,
            date_of_birth=date(1992, 4, 15),
            gender='female',
            default_address='123 Patient Street'
        )

    def test_patient_registration_success(self):
        response = self.client.post(reverse('patient_register'), {
            'full_name': 'Alice Walker',
            'email': 'alice.walker@example.com',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
            'date_of_birth': '1995-04-12',
            'gender': 'female',
            'contact_number': '+1 555-4433',
            'default_address': '10 Maple Court, Metro City',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='alice.walker@example.com')
        self.assertEqual(user.role, 'patient')
        self.assertTrue(user.is_patient)
        self.assertEqual(user.patient_profile.default_address, '10 Maple Court, Metro City')

    def test_patient_registration_password_mismatch(self):
        response = self.client.post(reverse('patient_register'), {
            'full_name': 'Bob Walker',
            'email': 'bob.walker@example.com',
            'password': 'PasswordOne1!',
            'confirm_password': 'PasswordTwo2!',
            'date_of_birth': '1992-06-20',
            'gender': 'male',
            'contact_number': '+1 555-8899',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='bob.walker@example.com').exists())
        self.assertContains(response, "Passwords do not match.")

    def test_unauthorized_users_cannot_create_doctor_accounts(self):
        """
        Requirement 10.9: Unauthorized users cannot create doctor accounts.
        - Anonymous user accessing doctor_register returns 403 Forbidden.
        - Authenticated patient user accessing admin_doctor_create returns 403 Forbidden.
        """
        # Anonymous attempt
        anon_resp = self.client.get(reverse('doctor_register'))
        self.assertEqual(anon_resp.status_code, 403)

        anon_post = self.client.post(reverse('admin_doctor_create'), {
            'full_name': 'Dr. Hacker',
            'email': 'hacker@hospital.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
        })
        # Anonymous post to admin_doctor_create redirects to login
        self.assertEqual(anon_post.status_code, 302)

        # Authenticated patient attempt
        self.client.login(username='pat.test@smartcare.org', password='PatientPass123!')
        patient_resp = self.client.get(reverse('admin_doctor_create'))
        self.assertEqual(patient_resp.status_code, 403)

    def test_admin_can_add_doctor_manually_without_sample_doctors_reappearing(self):
        """
        Requirement 10.8: Doctors can be added manually without old sample doctors reappearing.
        """
        self.client.login(username='hospital.admin@smartcare.org', password='AdminPassword123!')
        
        # Admin visits doctor onboarding form
        get_resp = self.client.get(reverse('admin_doctor_create'))
        self.assertEqual(get_resp.status_code, 200)

        # Admin creates doctor
        post_resp = self.client.post(reverse('admin_doctor_create'), {
            'full_name': 'Dr. Meredith Grey',
            'email': 'meredith.grey@smartcare.org',
            'password': 'DoctorPass2026!',
            'confirm_password': 'DoctorPass2026!',
            'specialization': 'General Medicine',
            'qualification': 'MD (Internal Medicine), FACS',
            'registration_number': 'REG-GREY-1001',
            'experience_years': 8,
            'consultation_fee': '450.00',
            'contact_number': '+1 555-0999',
            'available_days_list': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            'work_start_time': '09:00:00',
            'work_end_time': '17:00:00',
            'slot_duration_minutes': 30,
            'is_active': True
        })
        self.assertEqual(post_resp.status_code, 302)

        doc = DoctorProfile.objects.get(registration_number='REG-GREY-1001')
        self.assertEqual(doc.user.email, 'meredith.grey@smartcare.org')
        self.assertEqual(doc.specialization, 'General Medicine')
        self.assertTrue(doc.is_active)
        self.assertEqual(doc.available_days, 'Mon,Tue,Wed,Thu,Fri')

        # Run seed_data command and verify it DOES NOT recreate old sample doctors
        call_command('seed_data')
        self.assertFalse(DoctorProfile.objects.filter(user__email='sarah.cardio@smartcare.org').exists())
        self.assertFalse(DoctorProfile.objects.filter(user__email='david.neuro@smartcare.org').exists())
        # The manually created doctor remains intact
        self.assertTrue(DoctorProfile.objects.filter(registration_number='REG-GREY-1001').exists())

    def test_role_based_access_control(self):
        self.client.login(username='pat.test@smartcare.org', password='PatientPass123!')

        # Patient cannot access emergency queue dashboard
        response = self.client.get(reverse('emergency_queue_dashboard'))
        self.assertEqual(response.status_code, 403)

        # Patient cannot access doctor dashboard
        doc_dash_resp = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(doc_dash_resp.status_code, 302)

        # Patient can access patient dashboard
        pat_dash_resp = self.client.get(reverse('patient_dashboard'))
        self.assertEqual(pat_dash_resp.status_code, 200)


class SmartCareCompleteRequirementTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin
        self.admin = User.objects.create_user(
            username='admin@smartcare.org',
            email='admin@smartcare.org',
            password='AdminPassword123!',
            role='admin',
            first_name='Admin',
            last_name='User',
            is_staff=True,
            is_superuser=True
        )

        # Patient Alice
        self.patient_alice = User.objects.create_user(
            username='alice@example.com',
            email='alice@example.com',
            password='AlicePassword123!',
            role='patient',
            first_name='Alice',
            last_name='Smith'
        )
        self.patient_profile_alice = PatientProfile.objects.create(
            user=self.patient_alice,
            date_of_birth=date(1990, 1, 1),
            gender='female',
            default_address='123 Main St'
        )

        # Patient Bob
        self.patient_bob = User.objects.create_user(
            username='bob@example.com',
            email='bob@example.com',
            password='BobPassword123!',
            role='patient',
            first_name='Bob',
            last_name='Jones'
        )
        self.patient_profile_bob = PatientProfile.objects.create(
            user=self.patient_bob,
            date_of_birth=date(1988, 3, 3),
            gender='male',
            default_address='456 Elm St'
        )

        # Doctor 1: Dr. Watson
        self.doctor_user_1 = User.objects.create_user(
            username='watson@smartcare.org',
            email='watson@smartcare.org',
            password='WatsonPassword123!',
            role='doctor',
            first_name='John',
            last_name='Watson'
        )
        self.doctor_profile_1 = DoctorProfile.objects.create(
            user=self.doctor_user_1,
            specialization='Cardiology',
            qualification='MD Cardiology',
            registration_number='DOC-WATSON-01',
            consultation_fee=500.00,
            available_days='Mon,Tue,Wed,Thu,Fri',
            is_active=True
        )

        # Doctor 2: Dr. House
        self.doctor_user_2 = User.objects.create_user(
            username='house@smartcare.org',
            email='house@smartcare.org',
            password='HousePassword123!',
            role='doctor',
            first_name='Gregory',
            last_name='House'
        )
        self.doctor_profile_2 = DoctorProfile.objects.create(
            user=self.doctor_user_2,
            specialization='Neurology',
            qualification='MD Neurology',
            registration_number='DOC-HOUSE-02',
            consultation_fee=700.00,
            available_days='Mon,Tue,Wed,Thu,Fri',
            is_active=True
        )

    # 1. Homepage loads successfully (status 200)
    def test_01_homepage_loads_successfully(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    # 2. Homepage displays all three login options
    def test_02_homepage_displays_all_three_login_options(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SmartCare – Healthcare Appointment & Emergency Management")
        self.assertContains(response, "LOGIN AS PATIENT")
        self.assertContains(response, "LOGIN AS DOCTOR")
        self.assertContains(response, "LOGIN AS ADMINISTRATOR")
        self.assertContains(response, reverse('patient_login'))
        self.assertContains(response, reverse('doctor_login'))
        self.assertContains(response, reverse('admin_login'))
        self.assertContains(response, reverse('patient_register'))

    # 3. Each login option opens the correct login page
    def test_03_each_login_option_opens_correct_login_page(self):
        resp_patient = self.client.get(reverse('patient_login'))
        self.assertEqual(resp_patient.status_code, 200)
        self.assertContains(resp_patient, "Patient Portal Sign In")

        resp_doctor = self.client.get(reverse('doctor_login'))
        self.assertEqual(resp_doctor.status_code, 200)
        self.assertContains(resp_doctor, "Doctor Portal Sign In")

        resp_admin = self.client.get(reverse('admin_login'))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "Hospital Administrator Sign In")

    # 4. Patient logs in and reaches patient dashboard
    def test_04_patient_logs_in_and_reaches_patient_dashboard(self):
        response = self.client.post(reverse('patient_login'), {
            'email': 'alice@example.com',
            'password': 'AlicePassword123!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertTrue(response.context['user'].is_patient)
        self.assertRedirects(response, reverse('patient_dashboard'))

    # 5. Doctor logs in and reaches doctor dashboard
    def test_05_doctor_logs_in_and_reaches_doctor_dashboard(self):
        response = self.client.post(reverse('doctor_login'), {
            'email': 'watson@smartcare.org',
            'password': 'WatsonPassword123!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertTrue(response.context['user'].is_doctor)
        self.assertRedirects(response, reverse('doctor_dashboard'))

    # 6. Administrator logs in and reaches administrator dashboard
    def test_06_administrator_logs_in_and_reaches_administrator_dashboard(self):
        response = self.client.post(reverse('admin_login'), {
            'email': 'admin@smartcare.org',
            'password': 'AdminPassword123!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertTrue(response.context['user'].is_admin)
        self.assertRedirects(response, reverse('administrator_dashboard'))

    # 7. Invalid credentials display error message
    def test_07_invalid_credentials_display_error_message(self):
        # Wrong password
        resp1 = self.client.post(reverse('patient_login'), {
            'email': 'alice@example.com',
            'password': 'WrongPassword!',
        })
        self.assertEqual(resp1.status_code, 200)
        self.assertContains(resp1, "Invalid email or password")

        # Wrong portal (doctor attempting to log in on patient portal)
        resp2 = self.client.post(reverse('patient_login'), {
            'email': 'watson@smartcare.org',
            'password': 'WatsonPassword123!',
        })
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, "This portal is reserved for patients")

        # Wrong portal (patient attempting to log in on doctor portal)
        resp3 = self.client.post(reverse('doctor_login'), {
            'email': 'alice@example.com',
            'password': 'AlicePassword123!',
        })
        self.assertEqual(resp3.status_code, 200)
        self.assertContains(resp3, "This portal is reserved for doctors")

        # Wrong portal (patient attempting to log in on administrator portal)
        resp4 = self.client.post(reverse('admin_login'), {
            'email': 'alice@example.com',
            'password': 'AlicePassword123!',
        })
        self.assertEqual(resp4.status_code, 200)
        self.assertContains(resp4, "Access Denied: This portal is reserved for hospital administrators")

    # 8. Patient cannot access doctor dashboard
    def test_08_patient_cannot_access_doctor_dashboard(self):
        self.client.login(username='alice@example.com', password='AlicePassword123!')
        response = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(response.status_code, 302)

    # 9. Doctor cannot access administrator dashboard
    def test_09_doctor_cannot_access_administrator_dashboard(self):
        self.client.login(username='watson@smartcare.org', password='WatsonPassword123!')
        response = self.client.get(reverse('administrator_dashboard'))
        self.assertEqual(response.status_code, 403)

    # 10. Ordinary user cannot access admin-only features
    def test_10_ordinary_user_cannot_access_admin_only_features(self):
        # Patient cannot access doctor creation
        self.client.login(username='alice@example.com', password='AlicePassword123!')
        resp_add = self.client.get(reverse('admin_doctor_create'))
        self.assertEqual(resp_add.status_code, 403)

        # Patient cannot access administrator dashboard
        resp_admin_dash = self.client.get(reverse('administrator_dashboard'))
        self.assertEqual(resp_admin_dash.status_code, 403)

    # 11. Administrator can add a doctor
    def test_11_administrator_can_add_a_doctor(self):
        self.client.login(username='admin@smartcare.org', password='AdminPassword123!')
        post_data = {
            'full_name': 'Dr. Beverly Crusher',
            'email': 'crusher@smartcare.org',
            'password': 'CrusherPassword123!',
            'confirm_password': 'CrusherPassword123!',
            'specialization': 'General Medicine',
            'qualification': 'MD Chief Medical Officer',
            'registration_number': 'DOC-CRUSHER-99',
            'experience_years': 12,
            'consultation_fee': '550.00',
            'contact_number': '+1 555-8765',
            'available_days_list': ['Mon', 'Tue', 'Wed', 'Thu'],
            'work_start_time': '08:30:00',
            'work_end_time': '16:30:00',
            'slot_duration_minutes': 30,
            'is_active': True,
        }
        response = self.client.post(reverse('admin_doctor_create'), post_data)
        self.assertEqual(response.status_code, 302)

        # Verify doctor user and doctor profile exist in database
        self.assertTrue(User.objects.filter(email='crusher@smartcare.org').exists())
        user = User.objects.get(email='crusher@smartcare.org')
        self.assertEqual(user.role, 'doctor')
        self.assertTrue(user.check_password('CrusherPassword123!'))  # securely hashed
        self.assertTrue(hasattr(user, 'doctor_profile'))
        self.assertEqual(user.doctor_profile.registration_number, 'DOC-CRUSHER-99')

    # 12. Newly created doctor can log in
    def test_12_newly_created_doctor_can_log_in(self):
        # First create the doctor via admin
        self.client.login(username='admin@smartcare.org', password='AdminPassword123!')
        self.client.post(reverse('admin_doctor_create'), {
            'full_name': 'Dr. Leonard McCoy',
            'email': 'mccoy@smartcare.org',
            'password': 'BonesPassword123!',
            'confirm_password': 'BonesPassword123!',
            'specialization': 'Cardiology',
            'qualification': 'MD Cardiology',
            'registration_number': 'DOC-MCCOY-1701',
            'experience_years': 15,
            'consultation_fee': '600.00',
            'contact_number': '+1 555-1701',
            'available_days_list': ['Mon', 'Tue', 'Wed'],
            'work_start_time': '09:00:00',
            'work_end_time': '17:00:00',
            'slot_duration_minutes': 30,
            'is_active': True,
        })
        self.client.logout()

        # Doctor logs in at doctor_login
        response = self.client.post(reverse('doctor_login'), {
            'email': 'mccoy@smartcare.org',
            'password': 'BonesPassword123!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].email, 'mccoy@smartcare.org')
        self.assertRedirects(response, reverse('doctor_dashboard'))

    # 13. Each doctor sees only their own appointments
    def test_13_each_doctor_sees_only_their_own_appointments(self):
        from appointments.models import Appointment
        from datetime import time, timedelta
        from django.utils import timezone
        target_date = timezone.localdate() + timedelta(days=1)
        if target_date.weekday() >= 5:
            target_date += timedelta(days=2)

        # Appointment for Doctor 1 (Watson) with Patient Alice
        Appointment.objects.create(
            doctor=self.doctor_profile_1,
            patient=self.patient_profile_alice,
            appointment_date=target_date,
            appointment_time=time(10, 0),
            status='SCHEDULED',
            consultation_reason='heart',
            health_concern='Palpitations and shortness of breath'
        )

        # Appointment for Doctor 2 (House) with Patient Bob
        Appointment.objects.create(
            doctor=self.doctor_profile_2,
            patient=self.patient_profile_bob,
            appointment_date=target_date,
            appointment_time=time(11, 0),
            status='SCHEDULED',
            consultation_reason='neurological',
            health_concern='Chronic migraine episodes'
        )

        # Log in as Doctor 1 (Watson)
        self.client.login(username='watson@smartcare.org', password='WatsonPassword123!')
        resp_watson = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(resp_watson.status_code, 200)
        self.assertContains(resp_watson, 'Alice Smith')
        self.assertNotContains(resp_watson, 'Bob Jones')
        self.assertNotContains(resp_watson, 'Chronic migraine episodes')

        # Log in as Doctor 2 (House)
        self.client.login(username='house@smartcare.org', password='HousePassword123!')
        resp_house = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(resp_house.status_code, 200)
        self.assertContains(resp_house, 'Bob Jones')
        self.assertNotContains(resp_house, 'Alice Smith')
        self.assertNotContains(resp_house, 'Palpitations and shortness of breath')

    # 14. Patient sees only their own appointments
    def test_14_patient_sees_only_their_own_appointments(self):
        from appointments.models import Appointment
        from datetime import time, timedelta
        from django.utils import timezone
        target_date = timezone.localdate() + timedelta(days=1)
        if target_date.weekday() >= 5:
            target_date += timedelta(days=2)

        Appointment.objects.create(
            doctor=self.doctor_profile_1,
            patient=self.patient_profile_alice,
            appointment_date=target_date,
            appointment_time=time(10, 0),
            status='SCHEDULED',
            consultation_reason='heart',
            health_concern='Routine cardiac checkup'
        )

        Appointment.objects.create(
            doctor=self.doctor_profile_2,
            patient=self.patient_profile_bob,
            appointment_date=target_date,
            appointment_time=time(11, 0),
            status='SCHEDULED',
            consultation_reason='neurological',
            health_concern='Neurology consultation for headache'
        )

        # Alice logs in
        self.client.login(username='alice@example.com', password='AlicePassword123!')
        resp_alice = self.client.get(reverse('patient_dashboard'))
        self.assertEqual(resp_alice.status_code, 200)
        self.assertContains(resp_alice, 'Dr. John Watson')
        self.assertContains(resp_alice, 'Cardiology')
        self.assertContains(resp_alice, 'Heart-related concern')
        self.assertNotContains(resp_alice, 'Dr. Gregory House')
        self.assertNotContains(resp_alice, 'Neurological concern')

        # Bob logs in
        self.client.login(username='bob@example.com', password='BobPassword123!')
        resp_bob = self.client.get(reverse('patient_dashboard'))
        self.assertEqual(resp_bob.status_code, 200)
        self.assertContains(resp_bob, 'Dr. Gregory House')
        self.assertContains(resp_bob, 'Neurology')
        self.assertContains(resp_bob, 'Neurological concern')
        self.assertNotContains(resp_bob, 'Dr. John Watson')
        self.assertNotContains(resp_bob, 'Heart-related concern')

    # 15. Logout works and terminates session
    def test_15_logout_works_and_terminates_session(self):
        self.client.login(username='alice@example.com', password='AlicePassword123!')
        resp = self.client.get(reverse('patient_dashboard'))
        self.assertEqual(resp.status_code, 200)

        # Log out
        resp_logout = self.client.get(reverse('logout'))
        self.assertRedirects(resp_logout, reverse('home'))

        # Accessing protected page now redirects to login
        resp_after = self.client.get(reverse('patient_dashboard'))
        self.assertEqual(resp_after.status_code, 302)
        self.assertIn(reverse('login'), resp_after.url)
