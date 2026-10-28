/**
 * SmartCare Appointment Booking & Dynamic Slot Manager
 */

document.addEventListener('DOMContentLoaded', () => {
  const dateInput = document.getElementById('id_appointment_date');
  const slotSelect = document.getElementById('id_appointment_time');
  const bufferSelect = document.getElementById('id_safety_buffer_minutes');
  const previewBox = document.getElementById('departure-preview-box');
  const doctorIdMeta = document.getElementById('booking-meta-doctor-id');

  if (!dateInput || !slotSelect) return;

  const doctorId = doctorIdMeta ? doctorIdMeta.value : null;

  // Listen for date changes to reload available slots
  dateInput.addEventListener('change', () => {
    fetchAvailableSlots();
  });

  // Listen for time or buffer change to preview departure
  slotSelect.addEventListener('change', () => {
    calculateDeparturePreview();
  });

  if (bufferSelect) {
    bufferSelect.addEventListener('change', () => {
      calculateDeparturePreview();
    });
  }

  window.triggerDeparturePreview = () => {
    calculateDeparturePreview();
  };

  function fetchAvailableSlots() {
    const selectedDate = dateInput.value;
    if (!doctorId || !selectedDate) return;

    slotSelect.disabled = true;
    slotSelect.innerHTML = '<option value="">Loading available slots...</option>';

    fetch(`/api/available-slots/?doctor_id=${doctorId}&date=${selectedDate}`)
      .then(response => response.json())
      .then(data => {
        slotSelect.innerHTML = '';
        if (data.slots && data.slots.length > 0) {
          slotSelect.disabled = false;
          data.slots.forEach(slot => {
            const opt = document.createElement('option');
            opt.value = slot.value;
            opt.textContent = slot.label;
            slotSelect.appendChild(opt);
          });
          calculateDeparturePreview();
        } else {
          slotSelect.disabled = true;
          const opt = document.createElement('option');
          opt.value = '';
          opt.textContent = 'No available slots for this date';
          slotSelect.appendChild(opt);
          if (previewBox) previewBox.style.display = 'none';
        }
      })
      .catch(err => {
        console.error('Failed to fetch doctor slots:', err);
        slotSelect.innerHTML = '<option value="">Error loading slots</option>';
        slotSelect.disabled = false;
      });
  }

  function calculateDeparturePreview() {
    if (!previewBox || !slotSelect.value || !dateInput.value) return;

    const latInput = document.getElementById('id_patient_origin_lat');
    const lngInput = document.getElementById('id_patient_origin_lng');
    const addressInput = document.getElementById('id_patient_origin_address');
    const destLat = document.getElementById('booking-meta-dest-lat')?.value;
    const destLng = document.getElementById('booking-meta-dest-lng')?.value;
    const destName = document.getElementById('booking-meta-dest-name')?.value;

    const payload = {
      appointment_date: dateInput.value,
      appointment_time: slotSelect.value,
      safety_buffer_minutes: bufferSelect ? bufferSelect.value : 15,
      origin_lat: latInput?.value || null,
      origin_lng: lngInput?.value || null,
      origin_address: addressInput?.value || '',
      dest_lat: destLat || null,
      dest_lng: destLng || null,
      dest_name: destName || 'Hospital Clinic'
    };

    fetch('/api/routing/estimate/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          previewBox.style.display = 'block';
          document.getElementById('prev-departure-time').textContent = data.recommended_departure_time_display || '--';
          document.getElementById('prev-travel-time').textContent = `${data.duration_minutes} mins (~${data.distance_km} km)`;
          document.getElementById('prev-arrival-time').textContent = data.estimated_arrival_time_display || '--';
          document.getElementById('prev-buffer').textContent = `${data.safety_buffer_minutes} mins buffer`;
          
          const noteEl = document.getElementById('prev-routing-note');
          if (noteEl) {
            noteEl.textContent = data.traffic_status_message;
          }
        }
      })
      .catch(err => {
        console.warn('Live preview calculation unavailable:', err);
      });
  }

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
});
