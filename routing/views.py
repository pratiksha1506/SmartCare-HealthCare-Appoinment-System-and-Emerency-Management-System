import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, date, time

from .services import RoutingService
from appointments.models import Appointment
from core.models import DoctorProfile


def parse_float_safe(val):
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


@login_required
def estimate_route_api(request):
    """
    API endpoint for calculating travel duration, distance, and departure time.
    Supports either ad-hoc estimation or updating an existing Appointment.
    """
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST.dict()
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Invalid request body.'}, status=400)
    else:
        data = request.GET.dict()

    appointment_id = data.get('appointment_id')
    origin_lat = parse_float_safe(data.get('origin_lat'))
    origin_lng = parse_float_safe(data.get('origin_lng'))
    origin_address = data.get('origin_address', '').strip()
    safety_buffer = data.get('safety_buffer_minutes')
    safety_buffer = int(safety_buffer) if safety_buffer else 15

    appointment = None
    significant_delay = False
    delay_warning = None

    if appointment_id:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        # Verify ownership / permission
        if request.user.is_patient and appointment.patient.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

        appt_date = appointment.appointment_date
        appt_time = appointment.appointment_time
        dest_lat = appointment.doctor.hospital_lat
        dest_lng = appointment.doctor.hospital_lng
        dest_name = appointment.doctor.hospital_name
        dest_address = appointment.doctor.hospital_address
        delayed_by = appointment.delayed_by_minutes

        # Fallback to existing appointment coordinates if not newly provided
        if origin_lat is None and appointment.patient_origin_lat:
            origin_lat = appointment.patient_origin_lat
        if origin_lng is None and appointment.patient_origin_lng:
            origin_lng = appointment.patient_origin_lng
        if not origin_address and appointment.patient_origin_address:
            origin_address = appointment.patient_origin_address
    else:
        # Ad-hoc estimation
        date_str = data.get('appointment_date')
        time_str = data.get('appointment_time')
        dest_lat = parse_float_safe(data.get('dest_lat')) or 12.971598
        dest_lng = parse_float_safe(data.get('dest_lng')) or 77.594562
        dest_name = data.get('dest_name', 'SmartCare Central Hospital')
        dest_address = data.get('dest_address', '100 Healthcare Blvd, Metro City')
        delayed_by = 0

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.now().date()
            if time_str:
                if len(time_str.split(':')) == 2:
                    time_str += ':00'
                appt_time = datetime.strptime(time_str, '%H:%M:%S').time()
            else:
                appt_time = (timezone.now() + timezone.timedelta(hours=2)).time()
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid date or time format.'}, status=400)

    # Perform routing calculation through backend service
    result = RoutingService.get_route_and_departure(
        appointment_date=appt_date,
        appointment_time=appt_time,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        dest_name=dest_name,
        dest_address=dest_address,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        origin_address=origin_address,
        safety_buffer_minutes=safety_buffer,
        delayed_by_minutes=delayed_by
    )

    # If updating an existing appointment, compare old vs new travel duration
    if appointment:
        old_duration = appointment.estimated_travel_duration_minutes
        if old_duration and result.duration_minutes >= old_duration + 10:
            significant_delay = True
            diff = result.duration_minutes - old_duration
            delay_warning = (
                f"Significant traffic delay detected: estimated travel time has increased by {diff} minutes "
                f"(from {old_duration}m to {result.duration_minutes}m). Your recommended departure time has been "
                f"advanced to {result.recommended_departure_time.strftime('%I:%M %p')} to maintain your safe arrival."
            )

        # Update and persist
        appointment.estimated_travel_duration_minutes = result.duration_minutes
        appointment.safety_buffer_minutes = result.safety_buffer_minutes
        appointment.recommended_departure_time = result.recommended_departure_time
        appointment.estimated_arrival_time = result.estimated_arrival_time
        appointment.routing_provider_used = result.provider
        appointment.routing_note = result.traffic_status_message
        appointment.last_travel_update = timezone.now()
        if origin_lat:
            appointment.patient_origin_lat = origin_lat
        if origin_lng:
            appointment.patient_origin_lng = origin_lng
        if origin_address:
            appointment.patient_origin_address = origin_address
        appointment.save()

    response_payload = result.to_dict()
    response_payload.update({
        'status': 'success',
        'significant_delay': significant_delay,
        'delay_warning': delay_warning,
        'appointment_id': appointment.id if appointment else None,
        'is_time_to_leave': appointment.is_time_to_leave if appointment else False,
    })

    return JsonResponse(response_payload)
