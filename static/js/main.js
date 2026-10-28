/**
 * SmartCare Main JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
  // Auto-dismiss or allow closing alert banners
  const closeAlerts = document.querySelectorAll('.alert-close');
  closeAlerts.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const alert = e.target.closest('.alert');
      if (alert) alert.remove();
    });
  });

  // Modal handlers
  document.querySelectorAll('[data-modal-open]').forEach(trigger => {
    trigger.addEventListener('click', (e) => {
      const modalId = trigger.getAttribute('data-modal-open');
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.classList.add('open');
      }
    });
  });

  document.querySelectorAll('[data-modal-close]').forEach(closer => {
    closer.addEventListener('click', (e) => {
      const modal = closer.closest('.modal-overlay');
      if (modal) {
        modal.classList.remove('open');
      }
    });
  });

  // Close modal when clicking backdrop
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.remove('open');
      }
    });
  });
});
