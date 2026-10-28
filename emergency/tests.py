from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta

from core.models import User, PatientProfile
from emergency.models import EmergencyPatient, PriorityAssessmentLog
from emergency.queue import EmergencyPriorityQueue


class EmergencyQueueAndAccessTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Clinical Staff User
        self.staff_user = User.objects.create_user(
            username='staff@hospital.org',
            email='staff@hospital.org',
            password='StaffPass123!',
            role='staff',
            is_staff=True
        )

        # Patient 1: Charlie
        self.user_charlie = User.objects.create_user(
            username='charlie@patient.org',
            email='charlie@patient.org',
            password='Password123!',
            role='patient'
        )
        self.patient_charlie = PatientProfile.objects.create(
            user=self.user_charlie,
            date_of_birth=date(1991, 7, 12),
            gender='male'
        )

        # Patient 2: Diana
        self.user_diana = User.objects.create_user(
            username='diana@patient.org',
            email='diana@patient.org',
            password='Password123!',
            role='patient'
        )
        self.patient_diana = PatientProfile.objects.create(
            user=self.user_diana,
            date_of_birth=date(1989, 11, 3),
            gender='female'
        )

        now = timezone.now()

        # Emergency Case 1: Charlie (Priority 2, arrived 30 mins ago)
        self.case_charlie = EmergencyPatient.objects.create(
            full_name='Charlie Davis',
            age=35,
            priority_level=2,
            arrival_time=now - timedelta(minutes=30),
            chief_complaint='Severe abdominal pain and fever',
            status='WAITING',
            patient_profile=self.patient_charlie,
            registered_by=self.staff_user
        )

        # Emergency Case 2: Diana (Priority 3, arrived 40 mins ago)
        self.case_diana = EmergencyPatient.objects.create(
            full_name='Diana Prince',
            age=28,
            priority_level=3,
            arrival_time=now - timedelta(minutes=40),
            chief_complaint='Wrist sprain with mild swelling',
            status='WAITING',
            patient_profile=self.patient_diana,
            registered_by=self.staff_user
        )

    def test_4_patient_cannot_view_another_patient_emergency_record(self):
        """
        Requirement 10.4: A patient cannot view another patient's emergency queue record.
        Charlie logs in. Charlie can view his own emergency status at /emergency/my-status/<case_charlie.id>/.
        Charlie attempts to view Diana's emergency status at /emergency/my-status/<case_diana.id>/.
        Must return 403 Forbidden.
        """
        self.client.login(username='charlie@patient.org', password='Password123!')

        # Own emergency status -> 200 OK
        resp_own = self.client.get(reverse('patient_emergency_status', args=[self.case_charlie.id]))
        self.assertEqual(resp_own.status_code, 200)
        self.assertContains(resp_own, "Emergency Queue Status Tracker")
        self.assertContains(resp_own, self.case_charlie.patient_code)
        # Verify privacy: does NOT display Diana's name or symptoms
        self.assertNotContains(resp_own, "Diana Prince")
        self.assertNotContains(resp_own, "Wrist sprain")

        # Accessing Diana's emergency status -> 403 Forbidden
        resp_other = self.client.get(reverse('patient_emergency_status', args=[self.case_diana.id]))
        self.assertEqual(resp_other.status_code, 403)

    def test_5_patients_cannot_assign_or_change_their_own_emergency_priority(self):
        """
        Requirement 10.5: Patients cannot assign or change their own emergency priority.
        Charlie (patient) attempts to POST to emergency_reassess endpoint.
        Returns 403 Forbidden.
        Only clinical staff can update priority with mandatory rationale.
        """
        self.client.login(username='charlie@patient.org', password='Password123!')

        # Attempt to upgrade self to Priority 1 (Critical)
        resp_patient = self.client.post(
            reverse('emergency_reassess', args=[self.case_charlie.id]),
            {'new_priority': '1', 'clinical_rationale': 'I want to be seen immediately'}
        )
        self.assertEqual(resp_patient.status_code, 403)
        self.case_charlie.refresh_from_db()
        self.assertEqual(self.case_charlie.priority_level, 2)  # Remains Priority 2

        # Now authorized clinical staff reassesses priority
        self.client.login(username='staff@hospital.org', password='StaffPass123!')
        resp_staff = self.client.post(
            reverse('emergency_reassess', args=[self.case_charlie.id]),
            {'new_priority': '1', 'clinical_rationale': 'Acute peritoneal signs and hypotensive shock noted'}
        )
        self.assertEqual(resp_staff.status_code, 302)
        self.case_charlie.refresh_from_db()
        self.assertEqual(self.case_charlie.priority_level, 1)  # Successfully updated

    def test_6_queue_positions_update_when_queue_changes(self):
        """
        Requirement 10.6: Queue positions update when the queue changes.
        Initial state:
        - Case Charlie: Priority 2 (Position #1)
        - Case Diana: Priority 3 (Position #2)
        Then a new Priority 1 (Critical) patient arrives.
        Positions must immediately update:
        - Critical patient: Position #1
        - Charlie: Shifts to Position #2 (1 patient ahead)
        - Diana: Shifts to Position #3 (2 patients ahead)
        """
        queue = EmergencyPriorityQueue.get_active_queue_from_db()
        
        pos_charlie_initial = queue.get_patient_queue_position(self.case_charlie.id)
        pos_diana_initial = queue.get_patient_queue_position(self.case_diana.id)

        self.assertEqual(pos_charlie_initial['position'], 1)
        self.assertEqual(pos_charlie_initial['patients_ahead'], 0)
        self.assertEqual(pos_diana_initial['position'], 2)
        self.assertEqual(pos_diana_initial['patients_ahead'], 1)

        # New Critical Patient arrives (STEMI resuscitation)
        case_critical = EmergencyPatient.objects.create(
            full_name='Edward Acute',
            age=64,
            priority_level=1,
            chief_complaint='Acute inferior STEMI, diaphoretic',
            status='WAITING'
        )

        # Re-query queue positions
        queue_updated = EmergencyPriorityQueue.get_active_queue_from_db()
        pos_critical = queue_updated.get_patient_queue_position(case_critical.id)
        pos_charlie_after = queue_updated.get_patient_queue_position(self.case_charlie.id)
        pos_diana_after = queue_updated.get_patient_queue_position(self.case_diana.id)

        # Critical patient takes position 1
        self.assertEqual(pos_critical['position'], 1)
        self.assertEqual(pos_critical['patients_ahead'], 0)

        # Charlie moved from #1 to #2
        self.assertEqual(pos_charlie_after['position'], 2)
        self.assertEqual(pos_charlie_after['patients_ahead'], 1)

        # Diana moved from #2 to #3
        self.assertEqual(pos_diana_after['position'], 3)
        self.assertEqual(pos_diana_after['patients_ahead'], 2)

        # When critical patient is admitted, positions shift back
        case_critical.status = 'ADMITTED'
        case_critical.save()

        queue_after_admission = EmergencyPriorityQueue.get_active_queue_from_db()
        pos_charlie_restored = queue_after_admission.get_patient_queue_position(self.case_charlie.id)
        self.assertEqual(pos_charlie_restored['position'], 1)
        self.assertEqual(pos_charlie_restored['patients_ahead'], 0)
