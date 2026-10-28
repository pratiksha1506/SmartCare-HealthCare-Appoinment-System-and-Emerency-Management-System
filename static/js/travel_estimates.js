/**
 * SmartCare Travel Estimates & Dynamic Journey Updates
 * Features:
 * - On-demand journey estimate refresh
 * - Delay detection and alert banner rendering
 * - Real-time "Time to Leave" countdown
 */

document.addEventListener('DOMContentLoaded', () => {
  const refreshBtns = document.querySelectorAll('.btn-refresh-journey');

  refreshBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const appointmentId = btn.getAttribute('data-appointment-id');
      if (!appointmentId) return;

      const originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '⏳ Recalculating route...';

      fetch('/api/routing/estimate/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
          appointment_id: appointmentId
        })
      })
        .then(res => res.json())
        .then(data => {
          btn.disabled = false;
          btn.innerHTML = originalHtml;

          if (data.status === 'success') {
            updateAppointmentDOM(appointmentId, data);
            
            if (data.significant_delay && data.delay_warning) {
              showDelayWarning(data.delay_warning);
            } else {
              showToastNotification('✓ Travel estimate updated with latest routing data.');
            }
          } else {
            alert('Failed to refresh journey estimate: ' + (data.message || 'Unknown error'));
          }
        })
        .catch(err => {
          btn.disabled = false;
          btn.innerHTML = originalHtml;
          console.error('Error refreshing journey:', err);
          alert('Could not connect to routing server. Please try again.');
        });
    });
  });

  function updateAppointmentDOM(appointmentId, data) {
    // Update departure time
    const depEl = document.getElementById(`apt-departure-${appointmentId}`);
    if (depEl && data.recommended_departure_time_display) {
      depEl.textContent = data.recommended_departure_time_display;
      depEl.classList.add('highlight-update');
      setTimeout(() => depEl.classList.remove('highlight-update'), 2000);
    }

    // Update travel duration
    const durEl = document.getElementById(`apt-duration-${appointmentId}`);
    if (durEl) {
      durEl.textContent = `${data.duration_minutes} mins (~${data.distance_km} km)`;
    }

    // Update arrival time
    const arrEl = document.getElementById(`apt-arrival-${appointmentId}`);
    if (arrEl && data.estimated_arrival_time_display) {
      arrEl.textContent = data.estimated_arrival_time_display;
    }

    // Update routing note
    const noteEl = document.getElementById(`apt-note-${appointmentId}`);
    if (noteEl) {
      noteEl.textContent = data.traffic_status_message;
    }

    // Update last updated timestamp
    const updatedEl = document.getElementById(`apt-last-update-${appointmentId}`);
    if (updatedEl) {
      const now = new Date();
      updatedEl.textContent = `Just now (${now.toLocaleTimeString()})`;
    }

    // If time to leave condition changed
    if (data.is_time_to_leave) {
      const banner = document.getElementById('dashboard-leave-banner');
      if (banner) {
        banner.style.display = 'flex';
      }
    }
  }

  function showDelayWarning(message) {
    let warningBox = document.getElementById('dynamic-delay-warning-box');
    if (!warningBox) {
      warningBox = document.createElement('div');
      warningBox.id = 'dynamic-delay-warning-box';
      warningBox.className = 'alert alert-warning';
      const container = document.querySelector('.container') || document.body;
      container.insertBefore(warningBox, container.firstChild);
    }
    warningBox.innerHTML = `
      <div>
        <strong>⚠️ Traffic Alert:</strong> ${message}
      </div>
      <button type="button" class="btn btn-sm btn-outline alert-close" onclick="this.parentElement.remove()">Dismiss</button>
    `;
    warningBox.scrollIntoView({ behavior: 'smooth' });
  }

  function showToastNotification(msg) {
    const toast = document.createElement('div');
    toast.className = 'alert alert-success';
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.style.boxShadow = 'var(--shadow-lg)';
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  function getCsrfToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, 10) === 'csrftoken=') {
          cookieValue = decodeURIComponent(cookie.substring(10));
          break;
        }
      }
    }
    return cookieValue;
  }
});
