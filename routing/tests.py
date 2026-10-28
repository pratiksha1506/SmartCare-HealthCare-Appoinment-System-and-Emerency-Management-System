from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import date, time, datetime, timedelta
import zoneinfo
from unittest.mock import patch
import requests

from core.models import User, PatientProfile, DoctorProfile
from appointments.models import Appointment
from routing.services import (
    RoutingService,
    SimulationRoutingProvider,
    GoogleMapsRoutingProvider,
    haversine_distance_km
)


class RoutingAndDepartureTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='pat.route@example.com',
            email='pat.route@example.com',
            password='PatPassword123!',
            role='patient'
        )
        self.patient = PatientProfile.objects.create(
            user=self.user,
            date_of_birth=date(1990, 1, 1),
            gender='male',
            default_address='123 Origin Blvd',
            default_lat=12.9352,
            default_lng=77.5348
        )

        self.doc_user = User.objects.create_user(
            username='doc.route@example.com',
            email='doc.route@example.com',
            password='DocPassword123!',
            role='doctor'
        )
        self.doctor = DoctorProfile.objects.create(
            user=self.doc_user,
            specialization='General Medicine',
            qualification='MBBS, MD',
            registration_number='MED-ROUTE-123',
            hospital_name='SmartCare Test Hospital',
            hospital_address='500 Clinic Road',
            hospital_lat=12.9716,
            hospital_lng=77.5946
        )

    def test_smart_departure_calculation_formula(self):
        """
        Tests the exact formula specified in Feature 7:
        Recommended Departure Time = Appointment Start Time - Estimated Travel Duration - Safety Buffer.
        Example from prompt:
        Appointment time: 11:00 AM
        Estimated journey: 40 minutes
        Safety buffer: 15 minutes
        Recommended departure: 10:05 AM
        """
        test_date = date(2026, 11, 15)
        test_time = time(11, 0)
        travel_duration = 40
        buffer_minutes = 15

        apt = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=test_date,
            appointment_time=test_time,
            safety_buffer_minutes=buffer_minutes
        )
        departure_dt = apt.calculate_departure_schedule(
            travel_duration_minutes=travel_duration,
            buffer_minutes=buffer_minutes
        )

        # 11:00 AM - 40m - 15m = 10:05 AM
        self.assertEqual(departure_dt.hour, 10)
        self.assertEqual(departure_dt.minute, 5)
        self.assertEqual(apt.recommended_departure_time.strftime('%I:%M %p'), '10:05 AM')
        # Estimated arrival = 10:05 AM + 40m = 10:45 AM (15 mins buffer before 11:00 AM)
        self.assertEqual(apt.estimated_arrival_time.strftime('%I:%M %p'), '10:45 AM')

    def test_simulated_routing_mode_without_api_keys(self):
        """
        Verifies system operates cleanly in simulation mode when no API keys are provided.
        Ensures results are flagged as simulated and traffic limitations are clearly disclosed.
        """
        result = RoutingService.get_route_and_departure(
            appointment_date=date(2026, 11, 15),
            appointment_time=time(14, 0),
            dest_lat=12.9716,
            dest_lng=77.5946,
            origin_lat=12.9352,
            origin_lng=77.5348,
            safety_buffer_minutes=15
        )

        self.assertTrue(result.is_simulated)
        self.assertEqual(result.provider, 'simulation')
        self.assertFalse(result.traffic_condition_available)
        self.assertIn("Simulated", result.traffic_status_message)
        self.assertGreater(result.duration_minutes, 0)
        self.assertGreater(result.distance_km, 0)

    def test_routing_api_failure_and_graceful_fallback(self):
        """
        Verifies that if an external provider (Google Maps) throws a network timeout or API error,
        the system catches it, falls back to simulation mode, and informs the caller.
        """
        with patch('requests.get', side_effect=requests.exceptions.Timeout("Connection timed out")):
            with self.settings(ROUTING_PROVIDER='google', GOOGLE_MAPS_API_KEY='fake-google-key'):
                result = RoutingService.get_route_and_departure(
                    appointment_date=date(2026, 11, 15),
                    appointment_time=time(15, 0),
                    dest_lat=12.9716,
                    dest_lng=77.5946,
                    origin_lat=12.9352,
                    origin_lng=77.5348,
                    safety_buffer_minutes=20
                )

                self.assertTrue(result.is_simulated)
                self.assertIn('fallback', result.provider)
                self.assertIsNotNone(result.error_message)
                self.assertIn('Connection timed out', result.error_message)
                self.assertIsNotNone(result.recommended_departure_time)

    def test_dynamic_refresh_api_detects_significant_delay(self):
        """
        Tests Feature 8: Dynamic travel updates.
        When route refresh yields a significant delay (+10 mins or more),
        it recalculates departure time and sets a warning alert message.
        """
        apt = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=timezone.localdate() + timedelta(days=2),
            appointment_time=time(16, 0),
            estimated_travel_duration_minutes=15,
            safety_buffer_minutes=15
        )
        apt.calculate_departure_schedule()
        apt.save()

        self.client.login(username='pat.route@example.com', password='PatPassword123!')

        # Mock the routing service to return a delayed journey duration (e.g. 35 mins vs previous 15 mins)
        with patch('routing.services.SimulationRoutingProvider.estimate', return_value=(35, 12.0, "Simulated delay")):
            response = self.client.post(
                reverse('api_estimate_route'),
                {'appointment_id': apt.id}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['status'], 'success')
            self.assertTrue(data['significant_delay'])
            self.assertIn("traffic delay detected", data['delay_warning'].lower())

            apt.refresh_from_db()
            self.assertEqual(apt.estimated_travel_duration_minutes, 35)

    def test_haversine_distance_calculation(self):
        # Known distance between two points (Bangalore MG Road to Whitefield ~15.2 km)
        dist = haversine_distance_km(12.9756, 77.6066, 12.9698, 77.7499)
        self.assertAlmostEqual(dist, 15.5, delta=1.0)
