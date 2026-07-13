/**
 * RMS — Main JavaScript
 * Shared utilities used across all pages
 */

// ── CSRF Token ────────────────────────────────────────────────────
function getCsrfToken() {
  return document.cookie.split(';')
    .find(c => c.trim().startsWith('csrftoken='))
    ?.split('=')[1] || '';
}

// ── AJAX Helper ───────────────────────────────────────────────────
async function rmsPost(url, data) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(data),
  });
  return response;
}

// ── Toast Notifications ───────────────────────────────────────────
function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }

  const icons = {
    success: 'bi-check-circle-fill',
    error: 'bi-x-circle-fill',
    danger: 'bi-x-circle-fill',
    warning: 'bi-exclamation-triangle-fill',
    info: 'bi-info-circle-fill'
  };
  const icon = icons[type] || icons.info;

  const toast = document.createElement('div');
  toast.className = `rms-toast rms-toast-${type}`;
  
  toast.innerHTML = `
    <span class="rms-toast-icon"><i class="bi ${icon}"></i></span>
    <span class="rms-toast-message">${message}</span>
    <button class="rms-toast-close" aria-label="Close toast">
      <i class="bi bi-x"></i>
    </button>
  `;

  const dismiss = () => {
    toast.classList.add('rms-toast-leaving');
    toast.addEventListener('animationend', () => {
      toast.remove();
    }, { once: true });
    setTimeout(() => toast.remove(), 400); // fallback
  };

  toast.querySelector('.rms-toast-close').addEventListener('click', (e) => {
    e.stopPropagation();
    dismiss();
  });

  let timeoutId;
  const startTimer = () => {
    timeoutId = setTimeout(dismiss, duration);
  };
  const clearTimer = () => {
    clearTimeout(timeoutId);
  };

  toast.addEventListener('mouseenter', clearTimer);
  toast.addEventListener('mouseleave', startTimer);

  container.appendChild(toast);
  startTimer();
}

// ── Confirm Modal ─────────────────────────────────────────────────
function confirmAction(message, onConfirm) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay active';
  overlay.innerHTML = `
    <div class="rms-modal" style="max-width:380px;">
      <div class="rms-modal-header">
        <h3 class="rms-modal-title">⚠️ Confirm</h3>
      </div>
      <p style="font-size:0.85rem; color:var(--color-text-muted); margin-bottom:20px;">${message}</p>
      <div class="d-flex gap-2 justify-content-end">
        <button type="button" class="btn btn-secondary" id="cancelBtn">Cancel</button>
        <button type="button" class="btn btn-danger" id="confirmBtn">Confirm</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.querySelector('#cancelBtn').onclick = () => overlay.remove();
  overlay.querySelector('#confirmBtn').onclick = () => { overlay.remove(); onConfirm(); };
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
}

// ── Number formatting ─────────────────────────────────────────────
function formatNumber(n, decimals = 2) {
  return parseFloat(n).toFixed(decimals);
}

// ── Table sorting ─────────────────────────────────────────────────
function makeTableSortable(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const headers = table.querySelectorAll('thead th');
  headers.forEach((th, col) => {
    if (col === 0) return; // Disable sorting on serial number column
    th.style.cursor = 'pointer';
    th.title = 'Click to sort';
    let asc = true;
    th.addEventListener('click', () => {
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort((a, b) => {
        const aVal = a.cells[col]?.textContent.trim() || '';
        const bVal = b.cells[col]?.textContent.trim() || '';
        const aNum = parseFloat(aVal);
        const bNum = parseFloat(bVal);
        if (!isNaN(aNum) && !isNaN(bNum)) return asc ? aNum - bNum : bNum - aNum;
        return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      });
      rows.forEach(r => tbody.appendChild(r));
      headers.forEach(h => h.style.color = '');
      th.style.color = 'var(--color-gold)';
      asc = !asc;
    });
  });
}

// ── Initialize on DOM ready ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Sorting disabled
});
