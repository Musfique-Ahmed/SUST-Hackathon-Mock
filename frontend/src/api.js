// All API calls go through this base URL. In production the Nginx
// container reverse-proxies /api -> backend:8000, so the frontend uses
// a relative /api path by default.
const BASE = import.meta.env.VITE_API_BASE_URL || '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export function submitTicket(payload) {
  return request('/tickets', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listTickets() {
  return request('/tickets');
}