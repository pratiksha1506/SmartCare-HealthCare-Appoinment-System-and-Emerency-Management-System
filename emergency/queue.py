"""
Priority-Based Emergency Patient Queue Implementation.

Conforms to Features 3, 6, 7 & 8:
- Priority levels: 1 (Critical - Red), 2 (Urgent - Orange), 3 (Less Urgent - Green)
- Built on a genuine Python priority queue (heapq min-heap)
- Queue ordering:
    1. Critical patients first (Priority 1 < 2 < 3)
    2. Urgent patients second
    3. Less urgent patients third
    4. Within the same priority, patients waiting longer (earlier arrival timestamp) appear first.
- Database is the permanent source of truth; queue reconstructs dynamically from DB.
- Provides secure patient-specific position calculation without leaking other patients' data.
"""

import heapq
from typing import List, Optional, Tuple, Dict, Any
from django.utils import timezone
from .models import EmergencyPatient, PriorityAssessmentLog


class EmergencyQueueItem:
    """
    Wrapper for patients in the priority queue.
    Provides strict tuple comparison semantics:
    (priority_level, arrival_timestamp, patient_id)
    """
    def __init__(self, patient: EmergencyPatient):
        self.patient = patient
        self.priority = patient.priority_level
        self.arrival_timestamp = patient.arrival_time.timestamp()
        self.patient_id = patient.id

    def __lt__(self, other: 'EmergencyQueueItem') -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        if self.arrival_timestamp != other.arrival_timestamp:
            return self.arrival_timestamp < other.arrival_timestamp
        return self.patient_id < other.patient_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EmergencyQueueItem):
            return False
        return (self.priority == other.priority and
                self.arrival_timestamp == other.arrival_timestamp and
                self.patient_id == other.patient_id)

    def to_dict(self):
        return {
            'id': self.patient.id,
            'patient_code': self.patient.patient_code,
            'full_name': self.patient.full_name,
            'age': self.patient.age,
            'gender': self.patient.get_gender_display(),
            'priority_level': self.patient.priority_level,
            'priority_name': self.patient.priority_name,
            'status': self.patient.status,
            'status_display': self.patient.get_status_display(),
            'arrival_time': self.patient.arrival_time,
            'waiting_duration_display': self.patient.waiting_duration_display,
            'waiting_duration_seconds': self.patient.waiting_duration_seconds,
            'chief_complaint': self.patient.chief_complaint,
            'triage_notes': self.patient.triage_notes,
            'attending_doctor': str(self.patient.attending_clinician) if self.patient.attending_clinician else None,
        }


class EmergencyPriorityQueue:
    """
    Python Priority Queue wrapping heapq for emergency triage ordering.
    """
    def __init__(self):
        self._heap: List[EmergencyQueueItem] = []

    def clear(self):
        self._heap.clear()

    def push(self, patient: EmergencyPatient) -> bool:
        """
        Adds an eligible patient to the priority queue.
        Returns False if patient status is not WAITING or UNDER_ASSESSMENT.
        """
        if not patient.is_eligible_for_queue:
            return False
        item = EmergencyQueueItem(patient)
        heapq.heappush(self._heap, item)
        return True

    def pop(self) -> Optional[EmergencyPatient]:
        """Pops and returns the highest-priority patient waiting longest."""
        if not self._heap:
            return None
        item = heapq.heappop(self._heap)
        return item.patient

    def peek(self) -> Optional[EmergencyPatient]:
        """Returns highest priority patient without removing from queue."""
        if not self._heap:
            return None
        return self._heap[0].patient

    def size(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def rebuild_from_database(self, queryset=None) -> int:
        """
        Rebuilds the queue directly from the database to ensure state persistence
        and synchronization across application restarts and worker processes.
        """
        self.clear()
        if queryset is None:
            queryset = EmergencyPatient.objects.filter(
                status__in=['WAITING', 'UNDER_ASSESSMENT']
            ).order_by('priority_level', 'arrival_time')
            
        count = 0
        for patient in queryset:
            if patient.is_eligible_for_queue:
                self.push(patient)
                count += 1
        return count

    def get_sorted_queue(self) -> List[EmergencyPatient]:
        """
        Returns all current queue patients sorted by priority and arrival time.
        Does not mutate the internal heap.
        """
        sorted_items = sorted(self._heap)
        return [item.patient for item in sorted_items]

    def get_queue_display_data(self) -> List[dict]:
        """Returns patient dictionaries formatted for clinical dashboard display."""
        sorted_items = sorted(self._heap)
        return [item.to_dict() for item in sorted_items]

    def get_patient_queue_position(self, patient_id: int) -> Dict[str, Any]:
        """
        Calculates position and count of patients ahead for a specific patient.
        Preserves patient privacy: returns only this patient's metrics without exposing others.
        """
        sorted_patients = self.get_sorted_queue()
        for idx, p in enumerate(sorted_patients):
            if p.id == patient_id:
                return {
                    'found': True,
                    'in_active_queue': True,
                    'position': idx + 1,
                    'patients_ahead': idx,
                    'total_in_queue': len(sorted_patients),
                    'patient_code': p.patient_code,
                    'priority_level': p.priority_level,
                    'priority_name': p.priority_name,
                    'status': p.status,
                    'status_display': p.get_status_display(),
                    'arrival_time': p.arrival_time,
                    'waiting_duration_display': p.waiting_duration_display,
                    'disclaimer': 'Queue positions fluctuate dynamically as critical resuscitations take precedence over standard arrivals. Please follow clinical staff instructions.'
                }

        # If not in active queue, fetch state from database
        try:
            p = EmergencyPatient.objects.get(id=patient_id)
            return {
                'found': True,
                'in_active_queue': False,
                'position': None,
                'patients_ahead': 0,
                'total_in_queue': len(sorted_patients),
                'patient_code': p.patient_code,
                'priority_level': p.priority_level,
                'priority_name': p.priority_name,
                'status': p.status,
                'status_display': p.get_status_display(),
                'arrival_time': p.arrival_time,
                'waiting_duration_display': p.waiting_duration_display,
                'disclaimer': f'Patient is currently in status: {p.get_status_display()}.'
            }
        except EmergencyPatient.DoesNotExist:
            return {'found': False, 'in_active_queue': False}

    @classmethod
    def get_active_queue_from_db(cls) -> 'EmergencyPriorityQueue':
        """Convenience factory method that instantiates and rebuilds from DB."""
        eq = cls()
        eq.rebuild_from_database()
        return eq

    @staticmethod
    def reassess_priority(
        patient_id: int,
        new_priority: int,
        clinical_rationale: str,
        user=None
    ) -> Tuple[bool, Optional[EmergencyPatient], str]:
        """
        Reassesses a patient's clinical priority according to authorized staff findings.
        Persists to database, logs audit record, and returns the updated patient.
        """
        if new_priority not in [1, 2, 3]:
            return False, None, "Invalid clinical priority level. Must be 1 (Critical), 2 (Urgent), or 3 (Less Urgent)."

        try:
            patient = EmergencyPatient.objects.get(id=patient_id)
        except EmergencyPatient.DoesNotExist:
            return False, None, "Emergency patient not found."

        old_priority = patient.priority_level
        patient.priority_level = new_priority
        patient.save()

        # Log audit trail
        PriorityAssessmentLog.objects.create(
            emergency_patient=patient,
            previous_priority=old_priority,
            new_priority=new_priority,
            clinical_rationale=clinical_rationale,
            assessed_by=user if user and user.is_authenticated else None
        )

        return True, patient, f"Priority successfully updated from P{old_priority} to P{new_priority}."
