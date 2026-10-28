/**
 * SmartCare Patient Location & Geolocation Service
 * Adheres strictly to Feature 5:
 * - Clear explanation of purpose before requesting
 * - Explicit consent; option to decline
 * - Manual address fallback always available
 * - No continuous background tracking
 * - Graceful permission denial and error handling
 */

document.addEventListener('DOMContentLoaded', () => {
  const geoBtn = document.getElementById('btn-use-current-location');
  const latInput = document.getElementById('id_patient_origin_lat');
  const lngInput = document.getElementById('id_patient_origin_lng');
  const addressInput = document.getElementById('id_patient_origin_address');
  const statusDisplay = document.getElementById('location-status-message');
  const consentModal = document.getElementById('location-consent-modal');

  if (!geoBtn) return;

  geoBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (consentModal) {
      consentModal.classList.add('open');
    } else {
      requestDevicePosition();
    }
  });

  const confirmConsentBtn = document.getElementById('btn-confirm-location-consent');
  if (confirmConsentBtn) {
    confirmConsentBtn.addEventListener('click', () => {
      if (consentModal) consentModal.classList.remove('open');
      requestDevicePosition();
    });
  }

  const declineConsentBtn = document.getElementById('btn-decline-location-consent');
  if (declineConsentBtn) {
    declineConsentBtn.addEventListener('click', () => {
      if (consentModal) consentModal.classList.remove('open');
      if (statusDisplay) {
        statusDisplay.className = 'location-status';
        statusDisplay.innerHTML = 'Location access declined. Please enter your starting address manually in the field above.';
      }
    });
  }

  function requestDevicePosition() {
    if (!navigator.geolocation) {
      if (statusDisplay) {
        statusDisplay.className = 'location-status denied';
        statusDisplay.innerHTML = '⚠️ Geolocation is not supported by your browser. Please enter your starting address manually.';
      }
      return;
    }

    if (statusDisplay) {
      statusDisplay.className = 'location-status';
      statusDisplay.innerHTML = '⏳ Requesting your current coordinates...';
    }

    const geoOptions = {
      enableHighAccuracy: true,
      timeout: 8000,
      maximumAge: 60000 // Cached for up to 1 minute, no continuous tracking
    };

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;

        if (latInput) latInput.value = lat;
        if (lngInput) lngInput.value = lng;

        if (addressInput && !addressInput.value.trim()) {
          addressInput.value = `Current Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
        }

        if (statusDisplay) {
          statusDisplay.className = 'location-status success';
          statusDisplay.innerHTML = `✓ Location obtained successfully (${lat.toFixed(4)}, ${lng.toFixed(4)}). Route will be calculated to the hospital.`;
        }

        // Trigger departure recalculation preview if function exists
        if (typeof window.triggerDeparturePreview === 'function') {
          window.triggerDeparturePreview();
        }
      },
      (error) => {
        let msg = 'Could not retrieve your location.';
        switch (error.code) {
          case error.PERMISSION_DENIED:
            msg = 'Location permission was denied. You can enter your street address or neighborhood manually.';
            break;
          case error.POSITION_UNAVAILABLE:
            msg = 'Location information is currently unavailable. Please type your starting address manually.';
            break;
          case error.TIMEOUT:
            msg = 'Location request timed out. Please enter your address manually.';
            break;
        }

        if (statusDisplay) {
          statusDisplay.className = 'location-status denied';
          statusDisplay.innerHTML = `⚠️ ${msg}`;
        }
      },
      geoOptions
    );
  }
});
