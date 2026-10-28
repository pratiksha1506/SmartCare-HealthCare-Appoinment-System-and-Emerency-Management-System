"""
Routing Service and Departure Calculation Engine for SmartCare.

Features:
- Configurable routing backends: Google Maps Platform, Mapbox, or local Simulation.
- API keys retrieved securely from environment variables / Django settings.
- Never exposes secret keys to frontend JavaScript.
- Haversine-based simulation with realistic urban transit velocity when no key is set.
- Clear differentiation between live API data and simulated estimates.
- Explicit disclosure of traffic data limitations (no fabricated traffic).
- Departure calculation respecting hospital local timezone.
"""

import math
import logging
import requests
from datetime import datetime, timedelta
import zoneinfo
from typing import Optional, Dict, Any, Tuple

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two pairs of lat/lng coordinates in kilometers."""
    r = 6371.0  # Earth's radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


class RoutingResult:
    def __init__(
        self,
        duration_minutes: int,
        distance_km: float,
        provider: str,
        is_simulated: bool,
        traffic_condition_available: bool,
        traffic_status_message: str,
        recommended_departure_time: Optional[datetime] = None,
        estimated_arrival_time: Optional[datetime] = None,
        safety_buffer_minutes: int = 15,
        origin_display: str = "",
        destination_display: str = "",
        error_message: Optional[str] = None
    ):
        self.duration_minutes = duration_minutes
        self.distance_km = round(distance_km, 2)
        self.provider = provider
        self.is_simulated = is_simulated
        self.traffic_condition_available = traffic_condition_available
        self.traffic_status_message = traffic_status_message
        self.recommended_departure_time = recommended_departure_time
        self.estimated_arrival_time = estimated_arrival_time
        self.safety_buffer_minutes = safety_buffer_minutes
        self.origin_display = origin_display
        self.destination_display = destination_display
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            'duration_minutes': self.duration_minutes,
            'distance_km': self.distance_km,
            'provider': self.provider,
            'is_simulated': self.is_simulated,
            'traffic_condition_available': self.traffic_condition_available,
            'traffic_status_message': self.traffic_status_message,
            'recommended_departure_time': self.recommended_departure_time.isoformat() if self.recommended_departure_time else None,
            'recommended_departure_time_display': self.recommended_departure_time.strftime('%I:%M %p') if self.recommended_departure_time else None,
            'estimated_arrival_time': self.estimated_arrival_time.isoformat() if self.estimated_arrival_time else None,
            'estimated_arrival_time_display': self.estimated_arrival_time.strftime('%I:%M %p') if self.estimated_arrival_time else None,
            'safety_buffer_minutes': self.safety_buffer_minutes,
            'origin_display': self.origin_display,
            'destination_display': self.destination_display,
            'error_message': self.error_message,
        }


class SimulationRoutingProvider:
    """
    Local simulation provider that calculates realistic transit time
    without requiring external API credentials or incurring network latency.
    """
    def estimate(
        self,
        origin_lat: Optional[float],
        origin_lng: Optional[float],
        dest_lat: float,
        dest_lng: float,
        origin_address: str = "",
        dest_address: str = ""
    ) -> Tuple[int, float, str]:
        # If coordinates are missing, synthesize reasonable regional distance
        if origin_lat is None or origin_lng is None:
            distance_km = 8.5  # average metropolitan suburban trip
        else:
            distance_km = haversine_distance_km(origin_lat, origin_lng, dest_lat, dest_lng)
            # Route curvature factor: roads are ~1.25 to 1.35x longer than straight-line flight
            distance_km = max(1.0, distance_km * 1.3)

        # Average urban velocity ~30 km/h with traffic light dwell time (~5 mins)
        travel_hours = distance_km / 30.0
        minutes = int(math.ceil(travel_hours * 60)) + 6
        minutes = max(8, minutes)  # minimum 8 mins travel time

        note = "Simulated travel-time estimate (Live traffic data unavailable in simulation mode)"
        return minutes, distance_km, note


class GoogleMapsRoutingProvider:
    """
    Integrates with Google Maps Platform Directions API.
    Uses GOOGLE_MAPS_API_KEY from environment variables.
    """
    BASE_URL = "https://maps.googleapis.com/maps/api/directions/json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def estimate(
        self,
        origin_lat: Optional[float],
        origin_lng: Optional[float],
        dest_lat: float,
        dest_lng: float,
        origin_address: str = "",
        dest_address: str = ""
    ) -> Tuple[int, float, bool, str]:
        if origin_lat is not None and origin_lng is not None:
            origin_param = f"{origin_lat},{origin_lng}"
        elif origin_address:
            origin_param = origin_address
        else:
            raise ValueError("No valid origin coordinates or address provided for Google Maps.")

        dest_param = f"{dest_lat},{dest_lng}" if (dest_lat and dest_lng) else dest_address

        params = {
            'origin': origin_param,
            'destination': dest_param,
            'departure_time': 'now',
            'key': self.api_key,
        }

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=6.0)
            data = resp.json()

            if data.get('status') != 'OK' or not data.get('routes'):
                error_msg = data.get('error_message', data.get('status', 'No route found'))
                raise RuntimeError(f"Google Maps API error: {error_msg}")

            leg = data['routes'][0]['legs'][0]
            # Use duration_in_traffic if available, otherwise duration
            if 'duration_in_traffic' in leg:
                duration_seconds = leg['duration_in_traffic']['value']
                traffic_available = True
                traffic_note = "Live Google Maps traffic information active"
            else:
                duration_seconds = leg['duration']['value']
                traffic_available = False
                traffic_note = "Standard Google Maps duration (Live traffic data unavailable for this route)"

            distance_meters = leg['distance']['value']
            duration_minutes = max(1, int(math.ceil(duration_seconds / 60.0)))
            distance_km = distance_meters / 1000.0

            return duration_minutes, distance_km, traffic_available, traffic_note

        except Exception as e:
            logger.warning(f"Google Maps API call failed: {e}. Falling back to simulation.")
            raise e


class MapboxRoutingProvider:
    """
    Integrates with Mapbox Directions API.
    Uses MAPBOX_API_KEY from environment variables.
    """
    BASE_URL = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"

    def __init__(self, access_token: str):
        self.access_token = access_token

    def estimate(
        self,
        origin_lat: Optional[float],
        origin_lng: Optional[float],
        dest_lat: float,
        dest_lng: float,
        origin_address: str = "",
        dest_address: str = ""
    ) -> Tuple[int, float, bool, str]:
        if origin_lat is None or origin_lng is None:
            raise ValueError("Mapbox requires origin latitude and longitude coordinates.")

        coordinates = f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        url = f"{self.BASE_URL}/{coordinates}"
        params = {
            'access_token': self.access_token,
            'overview': 'false',
        }

        try:
            resp = requests.get(url, params=params, timeout=6.0)
            data = resp.json()

            if resp.status_code != 200 or not data.get('routes'):
                error_msg = data.get('message', f"HTTP {resp.status_code}")
                raise RuntimeError(f"Mapbox API error: {error_msg}")

            route = data['routes'][0]
            duration_seconds = route['duration']
            distance_meters = route['distance']
            duration_minutes = max(1, int(math.ceil(duration_seconds / 60.0)))
            distance_km = distance_meters / 1000.0
            traffic_note = "Live Mapbox traffic routing active"

            return duration_minutes, distance_km, True, traffic_note

        except Exception as e:
            logger.warning(f"Mapbox API call failed: {e}. Falling back to simulation.")
            raise e


class RoutingService:
    """
    Unified manager for routing requests, fallback recovery,
    and departure time calculations.
    """
    @classmethod
    def get_route_and_departure(
        cls,
        appointment_date,
        appointment_time,
        dest_lat: float,
        dest_lng: float,
        dest_name: str = "",
        dest_address: str = "",
        origin_lat: Optional[float] = None,
        origin_lng: Optional[float] = None,
        origin_address: str = "",
        safety_buffer_minutes: Optional[int] = None,
        delayed_by_minutes: int = 0,
    ) -> RoutingResult:
        if safety_buffer_minutes is None:
            safety_buffer_minutes = getattr(settings, 'DEFAULT_SAFETY_BUFFER_MINUTES', 15)

        configured_provider = getattr(settings, 'ROUTING_PROVIDER', 'simulation').lower()
        google_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '').strip()
        mapbox_key = getattr(settings, 'MAPBOX_API_KEY', '').strip()

        duration_minutes = 20
        distance_km = 8.0
        provider_used = 'simulation'
        is_simulated = True
        traffic_available = False
        traffic_note = "Simulated travel-time estimate (Live traffic unavailable in simulation mode)"
        error_msg = None

        if configured_provider == 'google' and google_key:
            try:
                g_provider = GoogleMapsRoutingProvider(google_key)
                duration_minutes, distance_km, traffic_available, traffic_note = g_provider.estimate(
                    origin_lat, origin_lng, dest_lat, dest_lng, origin_address, dest_address
                )
                provider_used = 'google'
                is_simulated = False
            except Exception as e:
                error_msg = f"Google Maps API failed ({str(e)}). Fallback simulation active."
                sim = SimulationRoutingProvider()
                duration_minutes, distance_km, traffic_note = sim.estimate(
                    origin_lat, origin_lng, dest_lat, dest_lng, origin_address, dest_address
                )
                provider_used = 'simulation (fallback)'
                is_simulated = True
                traffic_available = False
        elif configured_provider == 'mapbox' and mapbox_key and origin_lat is not None and origin_lng is not None:
            try:
                m_provider = MapboxRoutingProvider(mapbox_key)
                duration_minutes, distance_km, traffic_available, traffic_note = m_provider.estimate(
                    origin_lat, origin_lng, dest_lat, dest_lng, origin_address, dest_address
                )
                provider_used = 'mapbox'
                is_simulated = False
            except Exception as e:
                error_msg = f"Mapbox API failed ({str(e)}). Fallback simulation active."
                sim = SimulationRoutingProvider()
                duration_minutes, distance_km, traffic_note = sim.estimate(
                    origin_lat, origin_lng, dest_lat, dest_lng, origin_address, dest_address
                )
                provider_used = 'simulation (fallback)'
                is_simulated = True
                traffic_available = False
        else:
            # Native simulation provider
            sim = SimulationRoutingProvider()
            duration_minutes, distance_km, traffic_note = sim.estimate(
                origin_lat, origin_lng, dest_lat, dest_lng, origin_address, dest_address
            )
            provider_used = 'simulation'
            is_simulated = True
            traffic_available = False
            if configured_provider in ['google', 'mapbox']:
                traffic_note += f" (Provider '{configured_provider}' requested, but API key was not configured)."

        # Departure-time calculation respecting local timezone
        tz = zoneinfo.ZoneInfo(getattr(settings, 'TIME_ZONE', 'UTC'))
        base_dt = datetime.combine(appointment_date, appointment_time).replace(tzinfo=tz)
        if delayed_by_minutes > 0:
            base_dt += timedelta(minutes=delayed_by_minutes)

        total_offset = duration_minutes + safety_buffer_minutes
        recommended_departure_time = base_dt - timedelta(minutes=total_offset)
        estimated_arrival_time = recommended_departure_time + timedelta(minutes=duration_minutes)

        return RoutingResult(
            duration_minutes=duration_minutes,
            distance_km=distance_km,
            provider=provider_used,
            is_simulated=is_simulated,
            traffic_condition_available=traffic_available,
            traffic_status_message=traffic_note,
            recommended_departure_time=recommended_departure_time,
            estimated_arrival_time=estimated_arrival_time,
            safety_buffer_minutes=safety_buffer_minutes,
            origin_display=origin_address or f"Coordinates ({round(origin_lat, 4)}, {round(origin_lng, 4)})" if origin_lat else "Current Location",
            destination_display=dest_name or dest_address or "Hospital Clinic",
            error_message=error_msg
        )
